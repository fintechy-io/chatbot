import { useState, useRef, useEffect } from 'react';
import { Send, User, Bot } from 'lucide-react';
import { Link } from 'react-router-dom';
import MarkdownRenderer from '../components/MarkdownRenderer';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8923';

function ChatPage() {
  const [messages, setMessages] = useState([
    { id: 1, role: 'ai', content: 'Hello! I am your Image RAG assistant. Ask me questions about your ingested data!' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const messagesEndRef = useRef(null);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isChatLoading]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage = { id: Date.now(), role: 'user', content: inputValue.trim() };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsChatLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question: userMessage.content })
      });

      if (!response.ok) {
        throw new Error(`Chat failed: ${response.statusText}`);
      }

      const data = await response.json();
      const aiMessage = { id: Date.now() + 1, role: 'ai', content: data.answer };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      const errorMessage = { id: Date.now() + 1, role: 'ai', content: `Error: ${error.message}` };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  return (
    <div className="chat-area full-width">
      <div className="chat-header">
        <h1>Fintech AI Analyst</h1>
        <div style={{display: 'flex', alignItems: 'center', gap: '15px'}}>
            <span className="header-status">Online</span>
        </div>
      </div>

      <div className="messages-container">
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <div className={`avatar ${msg.role === 'user' ? 'user-avatar' : 'ai-avatar'}`}>
              {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
            </div>
            <div className="bubble">
              {msg.role === 'ai'
                ? <MarkdownRenderer>{msg.content}</MarkdownRenderer>
                : msg.content
              }
            </div>
          </div>
        ))}
        
        {isChatLoading && (
          <div className="message ai">
            <div className="avatar ai-avatar">
              <Bot size={20} />
            </div>
            <div className="bubble ai-loading-container">
              <div className="loading-spinner"></div>
              <span className="ai-loading-text">Analyzing data...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-container centered-input">
        <div className="input-box">
          <input 
            type="text" 
            placeholder="Ask a question about the uploaded documents..." 
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isChatLoading}
          />
          <button 
            className="send-button" 
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isChatLoading}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
