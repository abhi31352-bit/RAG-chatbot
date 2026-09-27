import React from 'react'
import { Link } from 'react-router-dom'
import { MessageCircle, Upload, BookOpen, Brain, Search } from 'lucide-react'

/**
 * Front door for the app.
 *
 * No `Header` here: `AppRoutes` renders it above the routed outlet so it
 * persists across navigation. Rendering a second one would put two nav bars on
 * this page.
 *
 * Every claim on this page is one the system actually keeps. In particular it
 * does not promise an answer to any question, because the more interesting
 * property is the opposite: it says when the course materials do not cover
 * something, and it cites the chunk each answer came from. Overstating the
 * product on the landing screen and then admitting ignorance in the transcript
 * is the combination that makes a demo look dishonest.
 */

const FEATURES = [
  {
    icon: Upload,
    title: 'Upload course materials',
    description:
      'Add PDFs, Word documents, Markdown and plain text. Each one is split into passages and indexed so it can be cited later.',
  },
  {
    icon: Search,
    title: 'Answers grounded in what you uploaded',
    description:
      'Every reply quotes the passages it used and links each one back to its source file, so a claim can be checked against the original.',
  },
  {
    icon: Brain,
    title: 'Says when it does not know',
    description:
      'If the material does not cover a question, the bot says so instead of filling the gap from its own memory. It also runs with no API key at all.',
  },
]

const STEPS = [
  {
    step: '1',
    title: 'Upload',
    desc: 'An instructor adds course materials in PDF, DOCX, TXT or MD.',
  },
  {
    step: '2',
    title: 'Index',
    desc: 'Documents are parsed, split into passages, and turned into vectors in a local store.',
  },
  {
    step: '3',
    title: 'Ask',
    desc: 'A student types a question in ordinary language.',
  },
  {
    step: '4',
    title: 'Answer',
    desc: 'The most relevant passages are retrieved and a grounded answer is written, with citations.',
  },
]

export const LandingPage: React.FC = () => {
  return (
    // `h-full overflow-y-auto` because the app shell is `h-screen`; without it
    // this taller-than-viewport page would be clipped rather than scrollable.
    <div className="h-full overflow-y-auto bg-gradient-to-b from-blue-50 to-white">
      <main>
        <section className="mx-auto max-w-4xl px-4 py-20 text-center">
          <h1 className="mb-4 text-4xl font-bold text-gray-900">
            Ask your course materials anything
          </h1>
          <p className="mx-auto mb-8 max-w-2xl text-lg text-gray-600">
            A retrieval-augmented chatbot that answers questions using the documents you
            uploaded, and shows you which passage each answer came from.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              to="/chat"
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 font-medium text-white transition-colors hover:bg-blue-700"
            >
              <MessageCircle className="h-5 w-5" aria-hidden="true" />
              Start chatting
            </Link>
            <Link
              to="/admin"
              className="flex items-center gap-2 rounded-xl border border-gray-300 px-6 py-3 font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              <Upload className="h-5 w-5" aria-hidden="true" />
              Upload documents
            </Link>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-4 pb-16">
          <div className="grid gap-6 md:grid-cols-3">
            {FEATURES.map((feature) => {
              const Icon = feature.icon
              return (
                <div key={feature.title} className="rounded-2xl border bg-white p-6 shadow-sm">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100">
                    <Icon className="h-6 w-6 text-blue-600" aria-hidden="true" />
                  </div>
                  <h3 className="mb-2 text-lg font-semibold text-gray-900">{feature.title}</h3>
                  <p className="text-sm text-gray-600">{feature.description}</p>
                </div>
              )
            })}
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-4 pb-20">
          <h2 className="mb-8 text-center text-2xl font-bold text-gray-900">How it works</h2>
          <div className="space-y-4">
            {STEPS.map((item) => (
              <div key={item.step} className="flex items-start gap-4 rounded-xl border bg-white p-4">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 font-semibold text-white">
                  {item.step}
                </div>
                <div>
                  <h3 className="font-medium text-gray-900">{item.title}</h3>
                  <p className="text-sm text-gray-600">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-4 pb-20 text-center">
          <div className="flex flex-col items-center gap-3 rounded-2xl border bg-white p-8 shadow-sm">
            <BookOpen className="h-6 w-6 text-blue-600" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-gray-900">Nothing indexed yet?</h2>
            <p className="max-w-md text-sm text-gray-600">
              The chatbot only knows what has been uploaded, and will tell you plainly when a
              question falls outside it. Add a document first, then ask.
            </p>
            <Link
              to="/admin"
              className="mt-2 flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-medium text-white transition-colors hover:bg-blue-700"
            >
              <Upload className="h-5 w-5" aria-hidden="true" />
              Add a document
            </Link>
          </div>
        </section>
      </main>
    </div>
  )
}
