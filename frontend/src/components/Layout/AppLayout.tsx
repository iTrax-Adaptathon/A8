import React from 'react';
import { Outlet } from 'react-router-dom';
import { AppHeader } from './AppHeader';
import { AppFooter } from './AppFooter';

export const AppLayout: React.FC = () => {
  return (
    <>
      <AppHeader />
      <main className="app-main">
        <Outlet />
      </main>
      <AppFooter />
    </>
  );
};
