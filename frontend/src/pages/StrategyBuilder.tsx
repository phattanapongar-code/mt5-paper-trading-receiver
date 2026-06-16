import { useState, useCallback, useEffect, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  addEdge,
  type Node,
  type Edge,
  type Connection,
} from '@xyflow/react'
import client from '../api/client'
import { useToast } from '../components/Toast'
import { useAuth } from '../context/AuthContext'
import Toolbar from '../components/strategy-builder/Toolbar'
import ConfigPanel from '../components/strategy-builder/ConfigPanel'
import { nodeTypes } from '../components/strategy-builder/nodes'
import { getDefaultParams, getNodeLabel, getNodeColor } from '../components/strategy-builder/utils'

export interface StrategyGraph {
  nodes: Array<{ id: string; type: string; params: Record<string, unknown>; position: { x: number; y: number } }>
  edges: Array<{ id: string; source: string; target: string; type?: string }>
}

export default function StrategyBuilder() {
  const { addToast } = useToast()
  const { isAuthenticated, loading } = useAuth()
  const reactFlowInstance = useReactFlow()

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [savedStrategies, setSavedStrategies] = useState<{ id: number; name: string; description: string }[]>([])
  const [strategyName, setStrategyName] = useState('')
  const [strategyDescription, setStrategyDescription] = useState('')
  const [selectedStrategyId, setSelectedStrategyId] = useState<number | null>(null)
  const [testBid, setTestBid] = useState('')
  const [testAsk, setTestAsk] = useState('')
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  // Fetch saved strategies
  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        const res = await client.get<{ id: number; name: string; description: string }[]>('/visual-strategies')
        setSavedStrategies(res.data)
      } catch {
        // ignore
      }
    }
    fetchStrategies()
  }, [])

  const onConnect = useCallback((params: Connection | Edge) => {
    const newEdge = {
      ...params,
      type: 'default',
    }
    setEdges((eds) => addEdge(newEdge, eds))
  }, [setEdges])

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    const type = event.dataTransfer.getData('application/reactflow')
    if (!type || !reactFlowWrapper.current) return

    const position = reactFlowInstance.screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    })

    const node = {
      id: `node_${Date.now()}`,
      type,
      position,
      data: {
        params: getDefaultParams(type as any),
        label: getNodeLabel(type as any),
        color: getNodeColor(type as any),
      },
      sourcePosition: 'right' as const,
      targetPosition: 'left' as const,
      draggable: true,
      style: {
        width: type === 'order' ? 220 : 180,
      },
    }
    setNodes((nds) => [...nds, node])
  }, [reactFlowInstance, setNodes])

  const onNodeDragStop = useCallback((_event: MouseEvent | TouchEvent, node: Node) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === node.id ? { ...n, position: node.position } : n))
    )
  }, [setNodes])

  const updateNodeParams = useCallback(
    (nodeId: string, params: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, params } } : n))
      )
    },
    [setNodes]
  )

  const handleSave = useCallback(async () => {
    if (!strategyName.trim()) {
      addToast('Please enter a strategy name', 'error')
      return
    }

    const graph = {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type,
        params: n.data.params,
        position: n.position,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
      })),
    }

    try {
      const res = await client.post<{ id: number }>('/visual-strategies', {
        name: strategyName,
        description: strategyDescription,
        graph,
      })
      addToast(`Strategy "${res.data.id}" saved successfully!`, 'success')
      setSavedStrategies((prev) => [
        ...prev,
        { id: res.data.id, name: strategyName, description: strategyDescription },
      ])
      setSelectedStrategyId(res.data.id)
      setStrategyName('')
      setStrategyDescription('')
    } catch (err: unknown) {
      addToast('Failed to save: ' + (err instanceof Error ? err.message : String(err)), 'error')
    }
  }, [nodes, edges, strategyName, strategyDescription, addToast])

  const handleLoad = useCallback(
    async (id: number) => {
      try {
        const res = await client.get<{ name: string; description: string; graph: { nodes: any[]; edges: any[] } }>(
          `/visual-strategies/${id}`
        )
        const { graph, name, description } = res.data

        const loadedNodes = graph.nodes.map((n: any) => ({
          id: n.id,
          type: n.type,
          position: n.position as any,
          data: { params: n.params, label: n.type, color: '#707a8a' },
          sourcePosition: 'right' as any,
          targetPosition: 'left' as any,
          style: { width: n.type === 'order' ? 220 : 180 },
        }))

        setNodes(loadedNodes)

        setEdges(
          graph.edges.map((e: any) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            type: e.type,
          }))
        )

        setStrategyName(name)
        setStrategyDescription(description)
        setSelectedStrategyId(id)
        addToast(`Loaded strategy "${name}"`, 'success')
      } catch (err: unknown) {
        addToast('Failed to load strategy: ' + (err instanceof Error ? err.message : String(err)), 'error')
      }
    },
    [addToast]
  )

  const handleTest = useCallback(async () => {
    if (nodes.length === 0) {
      addToast('Add at least one node to test', 'error')
      return
    }

    const graph = {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type,
        params: n.data.params,
        position: n.position,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
      })),
    }

    const bid = parseFloat(testBid)
    const ask = parseFloat(testAsk)
    if (isNaN(bid) || isNaN(ask) || bid <= 0 || ask <= 0) {
      addToast('Enter valid bid/ask prices for testing', 'error')
      return
    }

    try {
      const res = await client.post<{ decision: Record<string, unknown> | null }>(
        '/visual-strategies/test',
        {
          graph,
          bid,
          ask,
          symbol: 'XAUUSD',
          timeframe: 'M15',
        }
      )
      const decision = res.data.decision
      if (!decision) {
        addToast('No action (decision is null)', 'info')
      } else {
        const side = String(decision.action ?? '?').toUpperCase()
        const entry = Number(decision.entry ?? 0).toFixed(2)
        const sl = Number(decision.stop_loss ?? 0).toFixed(2)
        const tp = Number(decision.take_profit ?? 0).toFixed(2)
        addToast(`${side} @ ${entry} | SL: ${sl} | TP: ${tp}`, 'info')
      }
    } catch (err: unknown) {
      addToast('Test failed: ' + (err instanceof Error ? err.message : String(err)), 'error')
    }
  }, [nodes, edges, addToast, testBid, testAsk])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-canvas-dark">
        <div className="animate-pulse text-muted text-sm font-mono">Initializing...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas-dark">
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 max-w-md text-center">
          <h1 className="text-4xl font-bold text-primary mb-2">404</h1>
          <p className="text-sm text-muted mb-6">This page doesn't exist</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-canvas-dark">
      {/* Toolbar */}
      <Toolbar />

      {/* Main Canvas Area */}
      <div className="flex-1 flex flex-col relative">
        {/* Header */}
        <div className="h-14 bg-surface-card-dark border-b border-hairline-on-dark px-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">Strategy Name:</label>
            <input
              type="text"
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              placeholder="Enter strategy name..."
              className="px-3 py-1 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body outline-none w-64"
            />
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">Description:</label>
            <input
              type="text"
              value={strategyDescription}
              onChange={(e) => setStrategyDescription(e.target.value)}
              placeholder="Enter description..."
              className="px-3 py-1 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body outline-none w-80"
            />
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <select
              value={selectedStrategyId ?? ''}
              onChange={(e) => {
                const id = e.target.value ? Number(e.target.value) : null
                if (id) handleLoad(id)
                else setSelectedStrategyId(null)
              }}
              className="px-3 py-1 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body outline-none"
            >
              <option value="">Select saved strategy...</option>
              {savedStrategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Canvas */}
        <div ref={reactFlowWrapper} className="flex-1 relative overflow-hidden" onDragOver={onDragOver} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={onNodeDragStop}
            onNodeClick={(_, node) => setSelectedNode(node)}
            onPaneClick={() => setSelectedNode(null)}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background color="#2b3139" gap={12} size={1} />
            <Controls className="bg-surface-elevated-dark border border-hairline-on-dark text-body shadow-lg" />
            <MiniMap
              className="bg-surface-elevated-dark border border-hairline-on-dark text-body"
              nodeColor={(node) => {
                const color = node.data.color as string | undefined
                return color || '#0ecb81'
              }}
              maskColor="#0b0e11"
            />
          </ReactFlow>
        </div>

        {/* Bottom Bar */}
        <div className="h-10 bg-surface-card-dark border-t border-hairline-on-dark px-4 flex items-center gap-4 text-xs text-muted">
          <span>{nodes.length} nodes</span>
          <span className="text-hairline-on-dark">|</span>
          <span>{edges.length} edges</span>
          <div className="flex-1" />
          <label className="text-xs text-muted flex items-center gap-1">
            Bid:
            <input
              type="number"
              value={testBid}
              onChange={e => setTestBid(e.target.value)}
              placeholder="e.g. 2300"
              className="w-20 px-2 py-1 text-xs bg-canvas-dark border border-hairline-on-dark rounded text-body outline-none"
              step={0.01}
            />
          </label>
          <label className="text-xs text-muted flex items-center gap-1">
            Ask:
            <input
              type="number"
              value={testAsk}
              onChange={e => setTestAsk(e.target.value)}
              placeholder="e.g. 2300.5"
              className="w-20 px-2 py-1 text-xs bg-canvas-dark border border-hairline-on-dark rounded text-body outline-none"
              step={0.01}
            />
          </label>
          <button
            onClick={handleTest}
            className="px-3 py-1 text-xs bg-primary/20 text-primary border border-primary/50 rounded cursor-pointer disabled:opacity-50"
          >
            Test Strategy
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-1 text-xs bg-primary/20 text-primary border border-primary/50 rounded cursor-pointer disabled:opacity-50"
          >
            Save Strategy
          </button>
        </div>
      </div>

      {/* Config Panel */}
      {selectedNode && (
        <ConfigPanel
          node={selectedNode as any}
          onUpdate={updateNodeParams}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  )
}
