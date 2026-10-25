const API_BASE =
  import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    let message = 'Request failed';

    if (Array.isArray(data.detail)) {
      message = data.detail
        .map(err => {
          const field = Array.isArray(err.loc)
            ? err.loc[err.loc.length - 1]
            : 'field';

          return `${field}: ${err.msg}`;
        })
        .join('\n');
    } else if (typeof data.detail === 'string') {
      message = data.detail;
    } else if (data.detail) {
      message = JSON.stringify(data.detail);
    }

    throw new Error(message);
  }

  return data;
}

export const api = {
  register: (payload) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  login: (payload) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  lessons: (params = {}) =>
    request('/lessons?' + new URLSearchParams(params)),

  lesson: (id) =>
    request(`/lessons/${id}`),

  quizzes: (params = {}) =>
    request('/quizzes?' + new URLSearchParams(params)),

  quiz: (id) =>
    request(`/quizzes/${id}`),

  submitQuiz: (payload) =>
    request('/quiz-attempts', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  progress: (userId) =>
    request(`/progress/${userId}`),

  gamification: (userId) =>
    request(`/gamification/${userId}`),

  leaderboard: (params = {}) =>
    request('/leaderboard?' + new URLSearchParams(params)),

  completeLesson: (lessonId, userId) =>
    request(`/lessons/${lessonId}/complete`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId })
    }),

  updateProfile: (userId, payload) =>
    request(`/auth/profile/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }),

  chat: (payload) =>
    request('/chat', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  recommendations: (userId, params = {}) =>
    request(`/recommendations/${userId}?` + new URLSearchParams(params)),

  teacherClass: (teacherId, params = {}) =>
    request('/teacher/class?' + new URLSearchParams({ teacher_id: teacherId, ...params })),

  teacherStudent: (teacherId, studentId) =>
    request(`/teacher/students/${studentId}?` + new URLSearchParams({ teacher_id: teacherId })),

  health: () =>
    request('/health')
};