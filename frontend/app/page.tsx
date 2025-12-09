'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import SearchBar from '@/components/SearchBar';
import { createCourse, getJobStatus } from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (
    query: string,
    youtubeUrls?: string[],
    articleUrls?: string[]
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      // Create course
      const response = await createCourse({
        query,
        youtube_urls: youtubeUrls,
        article_urls: articleUrls,
      });

      if (response.status === 'completed' && response.course_id) {
        // Course created immediately, navigate to it
        router.push(`/courses/${response.course_id}`);
      } else {
        // Job is processing, poll for status
        await pollJobStatus(response.job_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to create course');
      setIsLoading(false);
    }
  };

  const pollJobStatus = async (jobId: string) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;

    const poll = async () => {
      try {
        const status = await getJobStatus(jobId);

        if (status.status === 'completed' && status.course_id) {
          router.push(`/courses/${status.course_id}`);
        } else if (status.status === 'failed') {
          setError('Course creation failed. Please try again.');
          setIsLoading(false);
        } else if (attempts < maxAttempts) {
          attempts++;
          setTimeout(poll, 5000); // Poll every 5 seconds
        } else {
          setError('Course creation is taking longer than expected. Please try again later.');
          setIsLoading(false);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to check job status');
        setIsLoading(false);
      }
    };

    poll();
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-gray-900">Seikna</h1>
          <p className="text-sm text-gray-600">Transform content into structured learning</p>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Learn from Multiple Sources
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Create structured, multi-source courses automatically from YouTube videos and articles
          </p>
        </div>

        {/* Search Bar */}
        <div className="mb-8">
          <SearchBar onSearch={handleSearch} isLoading={isLoading} />
        </div>

        {/* Error Message */}
        {error && (
          <div className="max-w-4xl mx-auto mb-8">
            <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
              {error}
            </div>
          </div>
        )}

        {/* Info Section */}
        <div className="max-w-4xl mx-auto mt-16">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-3xl mb-2">📚</div>
              <h3 className="font-semibold text-gray-900 mb-2">Multi-Source Learning</h3>
              <p className="text-sm text-gray-600">
                Combines information from multiple YouTube videos and articles
              </p>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">✅</div>
              <h3 className="font-semibold text-gray-900 mb-2">Verified Claims</h3>
              <p className="text-sm text-gray-600">
                Extracts and verifies knowledge claims from source materials
              </p>
            </div>
            <div className="text-center">
              <div className="text-3xl mb-2">📖</div>
              <h3 className="font-semibold text-gray-900 mb-2">Structured Courses</h3>
              <p className="text-sm text-gray-600">
                Automatically generates organized course content
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
