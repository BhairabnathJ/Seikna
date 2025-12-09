'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getCourse, Course } from '@/lib/api';

export default function CoursePage() {
  const params = useParams();
  const router = useRouter();
  const courseId = params.id as string;

  const [course, setCourse] = useState<Course | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (courseId) {
      loadCourse();
    }
  }, [courseId]);

  const loadCourse = async () => {
    try {
      setLoading(true);
      const data = await getCourse(courseId);
      setCourse(data);
      // Expand first section by default
      if (data.sections.length > 0) {
        setExpandedSections(new Set([data.sections[0].id]));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load course');
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (sectionId: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionId)) {
      newExpanded.delete(sectionId);
    } else {
      newExpanded.add(sectionId);
    }
    setExpandedSections(newExpanded);
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading course...</p>
          </div>
        </div>
      </main>
    );
  }

  if (error || !course) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-4 rounded-lg">
            {error || 'Course not found'}
          </div>
          <button
            onClick={() => router.push('/')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Back to Home
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => router.push('/')}
              className="text-blue-600 hover:text-blue-800"
            >
              ← Back to Home
            </button>
            <h1 className="text-xl font-bold text-gray-900">Seikna</h1>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-3">
            {/* Course Header */}
            <div className="bg-white rounded-lg border border-gray-200 p-8 mb-6">
              <h1 className="text-3xl font-bold text-gray-900 mb-4">{course.title}</h1>
              <p className="text-lg text-gray-600 mb-4">{course.description}</p>
              <div className="flex items-center gap-4 text-sm text-gray-500">
                <span>{course.metadata.source_count} source{course.metadata.source_count !== 1 ? 's' : ''}</span>
                {course.metadata.estimated_time && (
                  <>
                    <span>•</span>
                    <span>{course.metadata.estimated_time}</span>
                  </>
                )}
              </div>
            </div>

            {/* Course Sections */}
            <div className="space-y-4">
              {course.sections.map((section) => (
                <div
                  key={section.id}
                  className="bg-white rounded-lg border border-gray-200 overflow-hidden"
                >
                  <button
                    onClick={() => toggleSection(section.id)}
                    className="w-full px-6 py-4 text-left flex items-center justify-between hover:bg-gray-50 transition-colors"
                  >
                    <h2 className="text-xl font-semibold text-gray-900">{section.title}</h2>
                    <span className="text-gray-400">
                      {expandedSections.has(section.id) ? '▼' : '▶'}
                    </span>
                  </button>
                  {expandedSections.has(section.id) && (
                    <div className="px-6 py-4 border-t border-gray-200">
                      <div
                        className="prose max-w-none text-gray-700 whitespace-pre-wrap"
                        dangerouslySetInnerHTML={{ __html: section.content.replace(/\n/g, '<br />') }}
                      />
                      {section.sources.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-gray-200">
                          <p className="text-sm text-gray-500 mb-2">Sources:</p>
                          <div className="flex flex-wrap gap-2">
                            {section.sources.map((source, idx) => (
                              <span
                                key={idx}
                                className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded"
                              >
                                {source}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Glossary */}
            {course.glossary.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6 mt-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Glossary</h2>
                <dl className="space-y-4">
                  {course.glossary.map((term, idx) => (
                    <div key={idx}>
                      <dt className="font-semibold text-gray-900">{term.term}</dt>
                      <dd className="text-gray-600 mt-1">{term.definition}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg border border-gray-200 p-6 sticky top-20">
              <h3 className="font-semibold text-gray-900 mb-4">Course Info</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <span className="text-gray-500">Sources:</span>
                  <span className="ml-2 text-gray-900">{course.metadata.source_count}</span>
                </div>
                {course.metadata.estimated_time && (
                  <div>
                    <span className="text-gray-500">Estimated Time:</span>
                    <span className="ml-2 text-gray-900">{course.metadata.estimated_time}</span>
                  </div>
                )}
                <div>
                  <span className="text-gray-500">Sections:</span>
                  <span className="ml-2 text-gray-900">{course.sections.length}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

