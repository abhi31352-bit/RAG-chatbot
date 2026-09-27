import React from 'react'

interface SuggestedQuestionsProps {
  questions: string[]
  onSelect: (question: string) => void
  disabled?: boolean
}

export const SuggestedQuestions: React.FC<SuggestedQuestionsProps> = ({
  questions,
  onSelect,
  disabled = false,
}) => (
  <div className="flex flex-wrap justify-center gap-2 px-4 pb-2">
    {questions.map((question) => (
      <button
        key={question}
        type="button"
        onClick={() => onSelect(question)}
        disabled={disabled}
        className="rounded-full border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 transition-colors hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {question}
      </button>
    ))}
  </div>
)
