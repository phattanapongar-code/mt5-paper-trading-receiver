import ReplayViewer from '../components/ReplayViewer'

export default function Replay() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">Replay Simulation</h1>
      </div>
      <ReplayViewer />
    </div>
  )
}
