'use client';

import Link from 'next/link';

interface CourseCardProps {
  courseId: string;
  title: string;
  description: string;
  sourceCount: number;
  estimatedTime?: string;
}

export default function CourseCard({
  courseId,
  title,
  description,
  sourceCount,
  estimatedTime,
}: CourseCardProps) {
  return (
    <Link href={`/courses/${courseId}`}>
      <div className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow cursor-pointer">
        <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
        <p className="text-gray-600 mb-4 line-clamp-2">{description}</p>
        <div className="flex items-center gap-4 text-sm text-gray-500">
          <span>{sourceCount} source{sourceCount !== 1 ? 's' : ''}</span>
          {estimatedTime && <span>• {estimatedTime}</span>}
        </div>
      </div>
    </Link>
  );
}

