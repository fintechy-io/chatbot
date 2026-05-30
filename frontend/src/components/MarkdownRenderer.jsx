/**
 * Lightweight inline Markdown renderer.
 * Handles: **bold**, *italic*, headings, bullet lists, numbered lists,
 * horizontal rules (---), blockquotes (>), code (`inline`), and line breaks.
 * No external dependencies.
 */

function renderInline(text) {
  // Process inline markdown: bold, italic, inline code
  const parts = [];
  let remaining = text;
  let key = 0;

  // Regex: **bold**, *italic*, `code`
  const pattern = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)/g;
  let lastIndex = 0;
  let match;

  pattern.lastIndex = 0;
  while ((match = pattern.exec(remaining)) !== null) {
    if (match.index > lastIndex) {
      parts.push(remaining.slice(lastIndex, match.index));
    }
    if (match[1]) {
      parts.push(<strong key={key++}>{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(<em key={key++}>{match[4]}</em>);
    } else if (match[5]) {
      parts.push(<code key={key++} className="inline-code">{match[6]}</code>);
    }
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < remaining.length) {
    parts.push(remaining.slice(lastIndex));
  }
  return parts.length > 0 ? parts : [text];
}

export default function MarkdownRenderer({ children }) {
  if (!children) return null;

  const lines = children.split('\n');
  const elements = [];
  let i = 0;
  let keyCounter = 0;
  const k = () => keyCounter++;

  while (i < lines.length) {
    const line = lines[i];

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      elements.push(<hr key={k()} className="md-hr" />);
      i++;
      continue;
    }

    // Headings
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const Tag = `h${level}`;
      elements.push(<Tag key={k()} className={`md-h${level}`}>{renderInline(headingMatch[2])}</Tag>);
      i++;
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      elements.push(
        <blockquote key={k()} className="md-blockquote">
          {renderInline(line.slice(2))}
        </blockquote>
      );
      i++;
      continue;
    }

    // Unordered list — collect consecutive bullets
    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(<li key={k()}>{renderInline(lines[i].replace(/^[-*]\s+/, ''))}</li>);
        i++;
      }
      elements.push(<ul key={k()} className="md-ul">{items}</ul>);
      continue;
    }

    // Ordered list — collect consecutive numbered items
    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(<li key={k()}>{renderInline(lines[i].replace(/^\d+\.\s+/, ''))}</li>);
        i++;
      }
      elements.push(<ol key={k()} className="md-ol">{items}</ol>);
      continue;
    }

    // Empty line → spacer
    if (line.trim() === '') {
      elements.push(<div key={k()} className="md-spacer" />);
      i++;
      continue;
    }

    // Regular paragraph line
    elements.push(<p key={k()} className="md-p">{renderInline(line)}</p>);
    i++;
  }

  return <div className="markdown-body">{elements}</div>;
}
