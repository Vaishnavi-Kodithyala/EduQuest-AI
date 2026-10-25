import { createContext } from 'react';

// App-level navigation for the header. Pages used to pass their own
// callbacks, which drifted (the Dashboard button on a chapter page went back to
// the Lessons list). The header now reads one shared set from here.
export const NavContext = createContext(null);
