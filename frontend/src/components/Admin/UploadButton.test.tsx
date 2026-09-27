import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UploadButton } from './UploadButton'
import { validateFile } from './validateFile'
import type { UploadButtonProps } from './UploadButton'

function makeFile(name: string, type = 'text/plain', sizeBytes = 128): File {
  const file = new File(['x'.repeat(sizeBytes)], name, { type })
  // jsdom computes `size` from the blob, but redefining it keeps the tests
  // readable and lets the size limits be exercised without huge buffers.
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

function renderButton(overrides: Partial<UploadButtonProps> = {}) {
  const onUpload = vi.fn()
  const props: UploadButtonProps = {
    isUploading: false,
    uploadProgress: 0,
    uploadPhase: 'idle',
    onUpload,
    ...overrides,
  }
  return { onUpload, ...render(<UploadButton {...props} />) }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('validateFile', () => {
  it('accepts every type the backend allows', () => {
    for (const name of ['a.pdf', 'a.txt', 'a.docx', 'a.md', 'A.PDF']) {
      expect(validateFile(makeFile(name))).toBeNull()
    }
  })

  it('rejects an unsupported extension', () => {
    expect(validateFile(makeFile('slides.pptx'))).toContain('not a supported file type')
  })

  it('rejects a file with no extension', () => {
    expect(validateFile(makeFile('README'))).toContain('not a supported file type')
  })

  it('rejects a file over the size limit', () => {
    expect(validateFile(makeFile('big.pdf', 'application/pdf', 51 * 1024 * 1024))).toContain('50MB limit')
  })

  it('rejects an empty file rather than spending a request on it', () => {
    // The backend answers EMPTY_FILE for this, having already received a
    // 0-byte body; catching it here is instant.
    expect(validateFile(makeFile('blank.txt', 'text/plain', 0))).toContain('empty')
  })
})

describe('UploadButton', () => {
  it('uploads the chosen file', async () => {
    const user = userEvent.setup()
    const { onUpload } = renderButton()

    const file = makeFile('syllabus.txt')
    await user.upload(screen.getByLabelText('Choose a document to upload'), file)

    expect(onUpload).toHaveBeenCalledWith(file)
  })

  it('accepts drag and drop', async () => {
    // The plan's copy said "drag and drop" but shipped no drop handling, so
    // the advertised behaviour did not exist.
    const { onUpload } = renderButton()
    const file = makeFile('lecture.md')

    const zone = screen.getByText(/Drop a file here/i).closest('div')!
    const dataTransfer = {
      files: [file],
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      types: ['Files'],
    }
    fireEvent.drop(zone, { dataTransfer })

    expect(onUpload).toHaveBeenCalledWith(file)
  })

  it('reports a rejected file without calling the service', async () => {
    // `applyAccept: false` is required on the setup call: the input carries an
    // `accept` attribute, and userEvent discards files that do not match it,
    // so the change event would never fire and the component's own guard
    // would go untested.
    const user = userEvent.setup({ applyAccept: false })
    const { onUpload } = renderButton()

    await user.upload(screen.getByLabelText('Choose a document to upload'), makeFile('movie.mp4'))

    expect(onUpload).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveTextContent('not a supported file type')
  })

  it('shows upload progress while bytes are moving', () => {
    renderButton({ isUploading: true, uploadProgress: 40, uploadPhase: 'uploading' })

    const bar = screen.getByRole('progressbar', { name: 'Upload progress' })
    expect(bar).toHaveAttribute('aria-valuenow', '40')
    expect(screen.getByText('40%')).toBeInTheDocument()
  })

  it('switches to an indexing message once the bytes are all sent', () => {
    // The backend embeds inside the upload request, so a bar parked at 100%
    // with no explanation looks like a hang.
    renderButton({ isUploading: true, uploadProgress: 100, uploadPhase: 'indexing' })

    expect(screen.getByText('Indexing document…')).toBeInTheDocument()
    expect(screen.getByText(/Bytes received/)).toBeInTheDocument()
    expect(screen.queryByText('100%')).not.toBeInTheDocument()
  })

  it('hides the drop zone and disables the input while uploading', () => {
    renderButton({ isUploading: true, uploadProgress: 20, uploadPhase: 'uploading' })

    expect(screen.queryByText(/Drop a file here/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Choose a document to upload')).toBeDisabled()
  })

  it('opens the file picker from the browse button', async () => {
    const user = userEvent.setup()
    renderButton()

    const input = screen.getByLabelText('Choose a document to upload') as HTMLInputElement
    const clickSpy = vi.spyOn(input, 'click')

    await user.click(screen.getByRole('button', { name: 'browse' }))

    await waitFor(() => expect(clickSpy).toHaveBeenCalled())
  })
})
