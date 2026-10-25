import React, {useEffect, useState, useCallback} from 'react';
import {api} from './services/api';
import {levelFromGame} from './utils/gamify';
import {NavContext} from './context/nav';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Lessons from './pages/Lessons';
import LessonView from './pages/LessonView';
import Quiz from './pages/Quiz';
import Chat from './pages/Chat';
import Leaderboard from './pages/Leaderboard';
import TeacherDashboard from './pages/TeacherDashboard';
import ProfileSettings from './components/ProfileSettings';

export default function App(){
  const [user,setUser] = useState(()=>{
    let stored = null;
    try { stored = JSON.parse(localStorage.getItem('eduquest_user')||'null'); } catch { stored = null; }
    // EduQuest covers Grade 6 only. A browser still signed in from when
    // Grade 7 existed would otherwise ask for Grade 7 chapters and see none.
    return stored && stored.grade !== 6 ? { ...stored, grade: 6 } : stored;
  });
  const [page,setPage] = useState(user?'dashboard':'login');
  const [selectedLesson,setSelectedLesson] = useState(null);
  const [selectedQuiz,setSelectedQuiz] = useState(null);
  // XP, level, streak, badges and stats, all computed by the server.
  const [game,setGame] = useState(null);
  const [showSettings,setShowSettings] = useState(false);

  useEffect(()=>{
    if(!user) return;
    try { localStorage.setItem('eduquest_user',JSON.stringify(user)); } catch { /* private mode */ }
  },[user]);

  const isTeacher = user?.role === 'teacher';

  const refreshGame = useCallback(()=>{
    if(!user || user.role === 'teacher') return;
    api.gamification(user.id).then(setGame).catch(()=>{});
  },[user]);

  useEffect(()=>{ refreshGame(); },[refreshGame]);

  function logout(){
    try { localStorage.removeItem('eduquest_user'); } catch { /* ignore */ }
    setUser(null); setPage('login'); setGame(null);
  }

  if(!user){
    if(page==='register') return <Register onLogin={()=>setPage('login')} onRegistered={(u)=>{setUser(u);setPage('dashboard')}} />;
    return <Login onRegister={()=>setPage('register')} onLoggedIn={(u)=>{setUser(u);setPage('dashboard')}} />;
  }

  // Teachers see the class dashboard instead of the student pages.
  if(isTeacher) return <TeacherDashboard user={user} onLogout={logout} />;

  const level = levelFromGame(game);
  const streak = game?.streak?.current ?? 0;
  const completedLessons = game?.completed_lessons ?? [];

  const nav = (p)=>{ setPage(p); window.scrollTo(0, 0); };
  const navigation = {
    page,
    game,
    home: () => nav('dashboard'),
    lessons: () => nav('lessons'),
    leaderboard: () => nav('leaderboard'),
    chat: () => nav('chat'),
    settings: () => setShowSettings(true),
    logout
  };

  const shared = {
    user, level, streak, game, completedLessons,
    onLogout: logout,
    onChat: navigation.chat,
    onSettings: navigation.settings
  };

  const openLessonById = (ref) => {
    api.lesson(ref.id || ref.lesson_id).then(l => { setSelectedLesson(l); nav('lesson'); }).catch(()=>{});
  };
  // Every chapter's quiz has the id "q-<chapter id>".
  const openQuizForLesson = (lessonId) => {
    api.quiz(`q-${lessonId}`).then(q => { setSelectedQuiz(q); nav('quiz'); }).catch(()=>{});
  };

  let content;
  if(page==='chat') content = <Chat {...shared} onBack={navigation.home} onLessons={navigation.lessons} onOpenLesson={openLessonById}/>;
  else if(page==='lessons') content = <Lessons {...shared} onBack={navigation.home} onOpenLesson={(l)=>{setSelectedLesson(l);nav('lesson')}} onOpenQuiz={openQuizForLesson}/>;
  else if(page==='lesson') content = <LessonView {...shared} lesson={selectedLesson} onBack={navigation.lessons} onQuiz={(q)=>{setSelectedQuiz(q);nav('quiz')}} onCompleted={refreshGame}/>;
  else if(page==='quiz') content = <Quiz {...shared} quiz={selectedQuiz} onBack={()=>{navigation.lessons(); refreshGame();}} onSubmitted={refreshGame}/>;
  else if(page==='leaderboard') content = <Leaderboard {...shared}/>;
  else content = <Dashboard {...shared} onLessons={navigation.lessons} onLeaderboard={navigation.leaderboard} onOpenLesson={openLessonById} onOpenQuiz={openQuizForLesson}/>;

  // The settings panel overlays whichever page is open.
  return (
    <NavContext.Provider value={navigation}>
      {content}
      {showSettings && (
        <ProfileSettings
          user={user}
          game={game}
          onUpdated={setUser}
          onClose={()=>setShowSettings(false)}
        />
      )}
    </NavContext.Provider>
  );
}
