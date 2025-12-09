/**
 * API client for Seikna backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface CourseCreateRequest {
  query: string;
  num_sources?: number;
  source_types?: string[];
  difficulty?: string;
  youtube_urls?: string[];
  article_urls?: string[];
}

export interface CourseCreateResponse {
  job_id: string;
  status: string;
  estimated_time?: number;
  course_id?: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  course_id?: string;
  progress: number;
}

export interface Section {
  id: string;
  title: string;
  content: string;
  sources: string[];
}

export interface GlossaryTerm {
  term: string;
  definition: string;
}

export interface Course {
  course_id: string;
  title: string;
  description: string;
  metadata: {
    source_count: number;
    difficulty?: string;
    estimated_time?: string;
    vct_tier?: number;
  };
  sections: Section[];
  glossary: GlossaryTerm[];
}

export async function createCourse(request: CourseCreateRequest): Promise<CourseCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/courses/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create course');
  }

  return response.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/courses/jobs/${jobId}`);

  if (!response.ok) {
    throw new Error('Failed to get job status');
  }

  return response.json();
}

export async function getCourse(courseId: string): Promise<Course> {
  const response = await fetch(`${API_BASE_URL}/courses/${courseId}`);

  if (!response.ok) {
    throw new Error('Failed to get course');
  }

  return response.json();
}

