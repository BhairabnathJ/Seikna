'use client';

import { useState } from 'react';

interface SearchBarProps {
  onSearch: (query: string, youtubeUrls?: string[], articleUrls?: string[]) => void;
  isLoading?: boolean;
}

export default function SearchBar({ onSearch, isLoading = false }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [youtubeUrls, setYoutubeUrls] = useState('');
  const [articleUrls, setArticleUrls] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const youtubeList = youtubeUrls.split('\n').filter(url => url.trim());
    const articleList = articleUrls.split('\n').filter(url => url.trim());

    onSearch(
      query.trim(),
      youtubeList.length > 0 ? youtubeList : undefined,
      articleList.length > 0 ? articleList : undefined
    );
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-4xl mx-auto">
      <div className="flex flex-col gap-4">
        {/* Main search input */}
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What would you like to learn? (e.g., Machine Learning, Python Basics)"
            className="w-full px-6 py-4 text-lg rounded-lg border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
            disabled={isLoading}
          />
        </div>

        {/* Advanced options toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm text-blue-600 hover:text-blue-800 self-start"
        >
          {showAdvanced ? '▼' : '▶'} {showAdvanced ? 'Hide' : 'Show'} Advanced Options (URLs)
        </button>

        {/* Advanced URL inputs */}
        {showAdvanced && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                YouTube URLs (one per line)
              </label>
              <textarea
                value={youtubeUrls}
                onChange={(e) => setYoutubeUrls(e.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none font-mono text-sm"
                rows={4}
                disabled={isLoading}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Article URLs (one per line)
              </label>
              <textarea
                value={articleUrls}
                onChange={(e) => setArticleUrls(e.target.value)}
                placeholder="https://example.com/article..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:border-blue-500 focus:ring-1 focus:ring-blue-200 outline-none font-mono text-sm"
                rows={4}
                disabled={isLoading}
              />
            </div>
          </div>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? 'Creating Course...' : 'Create Course'}
        </button>
      </div>
    </form>
  );
}

