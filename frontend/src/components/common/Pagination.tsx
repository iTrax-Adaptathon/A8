import React from 'react';

interface PaginationProps {
  totalCount?: number;
  limit: number;
  offset: number;
  onPageChange: (newOffset: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({
  totalCount,
  limit,
  offset,
  onPageChange,
}) => {
  if (totalCount === undefined || totalCount <= limit) {
    return null;
  }

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(totalCount / limit);

  return (
    <div
      className="flex items-center justify-between"
      style={{
        padding: 'var(--space-sm) var(--space-md)',
        borderTop: '1px solid var(--outline-variant)',
        backgroundColor: 'var(--surface-container-low)',
      }}
    >
      <span className="text-label-sm" style={{ color: 'var(--on-surface-variant)' }}>
        Showing <strong className="font-tabular">{offset + 1}</strong> –{' '}
        <strong className="font-tabular">{Math.min(offset + limit, totalCount)}</strong> of{' '}
        <strong className="font-tabular">{totalCount}</strong> entries
      </span>

      <div className="flex items-center gap-xs">
        <button
          className="btn btn-outline btn-sm"
          disabled={offset === 0}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          title="Previous Page"
        >
          <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
            chevron_left
          </span>
          Previous
        </button>

        <span className="text-label-sm font-tabular" style={{ padding: '0 var(--space-sm)' }}>
          Page {currentPage} of {totalPages}
        </span>

        <button
          className="btn btn-outline btn-sm"
          disabled={offset + limit >= totalCount}
          onClick={() => onPageChange(offset + limit)}
          title="Next Page"
        >
          Next
          <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
            chevron_right
          </span>
        </button>
      </div>
    </div>
  );
};
