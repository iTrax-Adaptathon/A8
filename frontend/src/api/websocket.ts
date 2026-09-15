import { useState, useEffect, useRef } from 'react';
import { RealtimeMessage } from './types';

export type ConnectionState = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/api/v1/ws/capacity';

type EventCallback = (message: RealtimeMessage) => void;

class WebSocketManager {
  private socket: WebSocket | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private stateListeners: Set<(state: ConnectionState) => void> = new Set();
  private state: ConnectionState = 'DISCONNECTED';
  private reconnectTimeout: number | null = null;
  private retryDelay = 1000;
  private maxRetryDelay = 15000;

  constructor() {
    this.connect();
  }

  public getState(): ConnectionState {
    return this.state;
  }

  public onStateChange(listener: (state: ConnectionState) => void): () => void {
    this.stateListeners.add(listener);
    listener(this.state);
    return () => this.stateListeners.delete(listener);
  }

  private setState(newState: ConnectionState) {
    this.state = newState;
    this.stateListeners.forEach((l) => l(newState));
  }

  private connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.setState('CONNECTING');

    try {
      this.socket = new WebSocket(WS_URL);

      this.socket.onopen = () => {
        this.setState('CONNECTED');
        this.retryDelay = 1000;
      };

      this.socket.onmessage = (event) => {
        try {
          const message: RealtimeMessage = JSON.parse(event.data);
          this.dispatch(message);
        } catch {
          // Ignore non-JSON messages (e.g. ping/pong)
        }
      };

      this.socket.onclose = () => {
        this.setState('DISCONNECTED');
        this.scheduleReconnect();
      };

      this.socket.onerror = () => {
        this.socket?.close();
      };
    } catch {
      this.setState('DISCONNECTED');
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) return;
    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectTimeout = null;
      this.retryDelay = Math.min(this.retryDelay * 1.5, this.maxRetryDelay);
      this.connect();
    }, this.retryDelay);
  }

  private dispatch(message: RealtimeMessage) {
    // 1. Specific type listeners (e.g. "BED_UPDATED")
    const typeSet = this.listeners.get(message.type);
    if (typeSet) {
      typeSet.forEach((cb) => cb(message));
    }

    // 2. Resource type listeners (e.g. "BED", "STAFF")
    if (message.resourceType) {
      const resourceSet = this.listeners.get(`RESOURCE:${message.resourceType}`);
      if (resourceSet) {
        resourceSet.forEach((cb) => cb(message));
      }
    }

    // 3. Catch-all listeners
    const wildcardSet = this.listeners.get('*');
    if (wildcardSet) {
      wildcardSet.forEach((cb) => cb(message));
    }
  }

  public subscribe(eventType: string, callback: EventCallback): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);

    return () => {
      const set = this.listeners.get(eventType);
      if (set) {
        set.delete(callback);
        if (set.size === 0) {
          this.listeners.delete(eventType);
        }
      }
    };
  }
}

export const wsManager = new WebSocketManager();

export function useWebSocketState(): ConnectionState {
  const [state, setState] = useState<ConnectionState>(wsManager.getState());

  useEffect(() => {
    return wsManager.onStateChange(setState);
  }, []);

  return state;
}

export function useWebSocketEvent(
  eventTypeOrTypes: string | string[],
  callback: (msg: RealtimeMessage) => void
) {
  const savedCallback = useRef(callback);
  savedCallback.current = callback;

  useEffect(() => {
    const types = Array.isArray(eventTypeOrTypes) ? eventTypeOrTypes : [eventTypeOrTypes];
    const unsubs = types.map((t) =>
      wsManager.subscribe(t, (msg) => {
        savedCallback.current(msg);
      })
    );

    return () => {
      unsubs.forEach((unsub) => unsub());
    };
  }, [Array.isArray(eventTypeOrTypes) ? eventTypeOrTypes.join(',') : eventTypeOrTypes]);
}
