import React, { useState, useEffect, useRef } from 'react';
import { askChatbot, getScenes } from '../services/api';
import type { SceneResponse, ChatQueryResponse } from '../types';

interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  confidence?: number;
  evidence?: string[];
  context?: any;
  timestamp: string;
}

const SUGGESTED_QUERIES = [
  'Compare the two most recent scenes',
  'What objects are currently in the room?',
  'Where is the chair?',
  'What is near the laptop?',
  'What changes were detected recently?',
  'Summarize the environment',
];

export default function Query() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'bot',
      text: "👋 Hello! I am your **Cognitive Scene Memory Chatbot**.\n\nYou can ask me questions about **detected objects**, their **spatial relationships** (e.g. *what is on the desk?*), or **environment changes** when comparing scenes (e.g. *what was moved or added?*).",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [scenes, setScenes] = useState<SceneResponse[]>([]);
  const [selectedBeforeScene, setSelectedBeforeScene] = useState<string>('');
  const [selectedAfterScene, setSelectedAfterScene] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch available scenes for dropdown comparisons
  useEffect(() => {
    async function fetchScenes() {
      try {
        const list = await getScenes(20);
        setScenes(list);
        if (list.length >= 2) {
          setSelectedBeforeScene(list[1].scene_id);
          setSelectedAfterScene(list[0].scene_id);
        } else if (list.length === 1) {
          setSelectedAfterScene(list[0].scene_id);
        }
      } catch (err) {
        console.error('Failed to load scenes for comparison dropdown:', err);
      }
    }
    fetchScenes();
  }, []);

  // Auto-scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (queryText?: string, isCompareAction: boolean = false) => {
    const text = (queryText || inputQuery).trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setLoading(true);

    const isCompareQuery = isCompareAction || text.toLowerCase().includes('compare');

    try {
      const response: ChatQueryResponse = await askChatbot({
        query: text,
        scene_before_id: isCompareQuery ? selectedBeforeScene || undefined : undefined,
        scene_after_id: isCompareQuery ? selectedAfterScene || undefined : undefined,
      });

      const botMsg: Message = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: response.answer,
        confidence: response.confidence,
        evidence: response.supporting_evidence,
        context: response.context,
        timestamp: new Date(response.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      const errorMsg: Message = {
        id: `bot-err-${Date.now()}`,
        sender: 'bot',
        text: `⚠️ **Error**: ${err instanceof Error ? err.message : 'Could not retrieve answer from cognitive backend.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] space-y-4 animate-slide-up">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <h2 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <span>Cognitive Scene Chatbot</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20">
              AI Query Engine
            </span>
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            Ask questions about detected objects, spatial scene graphs, and environment change comparisons
          </p>
        </div>

        {/* Scene Comparison Selector Bar */}
        {scenes.length >= 2 && (
          <div className="flex items-center gap-2 text-xs bg-bg-card border border-border rounded-lg p-1.5 px-3">
            <span className="text-text-muted font-medium">Compare:</span>
            <select
              value={selectedBeforeScene}
              onChange={(e) => setSelectedBeforeScene(e.target.value)}
              className="bg-bg-secondary text-text-primary border border-border rounded px-2 py-1 text-xs focus:outline-none focus:border-accent-cyan font-mono"
            >
              {scenes.map((s) => (
                <option key={`before-${s.scene_id}`} value={s.scene_id}>
                  {s.scene_id} ({s.object_count} objs)
                </option>
              ))}
            </select>
            <span className="text-text-muted">➔</span>
            <select
              value={selectedAfterScene}
              onChange={(e) => setSelectedAfterScene(e.target.value)}
              className="bg-bg-secondary text-text-primary border border-border rounded px-2 py-1 text-xs focus:outline-none focus:border-accent-cyan font-mono"
            >
              {scenes.map((s) => (
                <option key={`after-${s.scene_id}`} value={s.scene_id}>
                  {s.scene_id} ({s.object_count} objs)
                </option>
              ))}
            </select>
            <button
              onClick={() => handleSend(`Compare scene ${selectedBeforeScene} and ${selectedAfterScene}`, true)}
              className="ml-1 px-2.5 py-1 rounded bg-accent-cyan/20 hover:bg-accent-cyan/30 text-accent-cyan font-medium transition"
            >
              Compare
            </button>
          </div>
        )}
      </div>

      {/* Suggested Queries Chips */}
      <div className="flex flex-wrap gap-1.5">
        <span className="text-xs text-text-muted self-center mr-1">Suggestions:</span>
        {SUGGESTED_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => handleSend(q)}
            disabled={loading}
            className="text-xs px-2.5 py-1 rounded-full bg-bg-card hover:bg-bg-secondary text-text-secondary hover:text-accent-cyan border border-border transition text-left"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4 glass-panel rounded-xl">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-2xl rounded-2xl p-4 text-sm leading-relaxed shadow-sm ${
                m.sender === 'user'
                  ? 'bg-accent-cyan text-bg-primary rounded-br-none font-medium'
                  : 'bg-bg-card border border-border text-text-primary rounded-bl-none'
              }`}
            >
              {/* Formatted Content */}
              <div className="whitespace-pre-wrap space-y-2">
                {m.text.split('\n').map((line, idx) => {
                  // Basic markdown formatting
                  let formatted = line;
                  const isHeader = line.startsWith('###');
                  if (isHeader) {
                    return (
                      <h4 key={idx} className="font-semibold text-accent-cyan mt-1 mb-1">
                        {line.replace(/^###\s*/, '')}
                      </h4>
                    );
                  }
                  return <p key={idx}>{formatted}</p>;
                })}
              </div>

              {/* Confidence & Evidence Badge */}
              {m.confidence !== undefined && (
                <div className="mt-3 pt-2 border-t border-border/40 flex flex-wrap items-center gap-2 text-xs text-text-muted">
                  <span className="px-2 py-0.5 rounded-full bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20">
                    {(m.confidence * 100).toFixed(0)}% Confidence
                  </span>

                  {m.evidence && m.evidence.length > 0 && (
                    <details className="w-full mt-1.5 cursor-pointer">
                      <summary className="text-[11px] text-accent-cyan hover:underline select-none">
                        View Supporting Evidence ({m.evidence.length})
                      </summary>
                      <ul className="mt-1 pl-4 list-disc text-[11px] text-text-muted space-y-0.5 font-mono">
                        {m.evidence.map((ev, i) => (
                          <li key={i}>{ev}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )}
            </div>
            <span className="text-[10px] text-text-muted px-1 mt-1 font-mono">{m.timestamp}</span>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-text-muted p-2">
            <div className="w-4 h-4 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
            <span>Consulting Cognitive Scene Memory...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="flex items-center gap-2 bg-bg-card border border-border rounded-xl p-2 px-3 shadow-lg">
        <input
          type="text"
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about detected objects, relations (e.g. 'is cup on table?'), or scene changes..."
          disabled={loading}
          className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
        />
        <button
          onClick={() => handleSend()}
          disabled={!inputQuery.trim() || loading}
          className="px-4 py-2 rounded-lg bg-accent-cyan hover:bg-accent-cyan/90 disabled:opacity-40 text-bg-primary font-semibold text-xs flex items-center gap-1.5 transition shadow"
        >
          <span>Ask</span>
          <span>➔</span>
        </button>
      </div>
    </div>
  );
}
