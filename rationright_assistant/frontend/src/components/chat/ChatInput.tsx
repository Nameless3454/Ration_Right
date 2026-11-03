import React, { useState, useRef, useEffect } from "react";
import { Send, CornerDownLeft, Sparkles } from "lucide-react";

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
  disabled = false,
}) => {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!input.trim() || isLoading || disabled) return;
    onSendMessage(input.trim());
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const suggestionChips = [
    "How many beneficiaries in latest import?",
    "Which records have duplicate flags?",
    "Highest complaint shops?",
    "What is statutory quota?",
  ];

  return (
    <div className="p-3 bg-white border-t border-slate-200 space-y-2">
      {/* Quick Action Chips */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] scrollbar-none">
        <Sparkles className="w-3.5 h-3.5 text-gov-600 shrink-0" />
        {suggestionChips.map((chip, i) => (
          <button
            key={i}
            type="button"
            disabled={isLoading || disabled}
            onClick={() => onSendMessage(chip)}
            className="whitespace-nowrap px-2.5 py-1 rounded-full bg-slate-100 hover:bg-gov-50 hover:text-gov-800 border border-slate-200 text-slate-700 transition disabled:opacity-50"
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Input Form */}
      <div className="relative flex items-end gap-1.5 bg-slate-50 border border-slate-300 rounded-xl p-1.5 focus-within:ring-2 focus-within:ring-gov-500 focus-within:border-transparent transition">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading || disabled}
          placeholder="Ask operational, beneficiary, inventory, or audit questions..."
          className="w-full resize-none bg-transparent px-2.5 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none max-h-28"
        />

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading || disabled}
          className="p-2 rounded-lg bg-gov-700 hover:bg-gov-600 text-white transition disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>

      <div className="flex items-center justify-between text-[10px] text-slate-400 px-1">
        <span>Press <strong>Enter</strong> to send, <strong>Shift+Enter</strong> for newline</span>
        <span>Answers grounded strictly in weekly imported datasets</span>
      </div>
    </div>
  );
};

