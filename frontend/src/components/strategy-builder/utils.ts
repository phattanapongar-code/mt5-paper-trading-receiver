import { type Node, Position } from '@xyflow/react'

export type NodeTypes = 
  | 'data_source' 
  | 'sma' 
  | 'rsi' 
  | 'atr' 
  | 'ema' 
  | 'compare' 
  | 'and' 
  | 'or' 
  | 'not' 
  | 'order'
  | 'value'
  | 'field'
  | 'trend'
  | 'ob_query'
  | 'bollinger'
  | 'macd'
  | 'price'
  | 'ob_in_range'
  | 'ob_not_stale'

export const getNodeLabel = (type: NodeTypes): string => {
  const labels: Record<NodeTypes, string> = {
    data_source: 'Data Source',
    sma: 'SMA',
    rsi: 'RSI',
    atr: 'ATR',
    ema: 'EMA',
    compare: 'Compare',
    and: 'AND',
    or: 'OR',
    not: 'NOT',
    order: 'Order',
    value: 'Value',
    field: 'Field',
    trend: 'Trend',
    ob_query: 'OB Query',
    bollinger: 'Bollinger',
    macd: 'MACD',
    price: 'Price',
    ob_in_range: 'OB In Range',
    ob_not_stale: 'OB Not Stale',
  }
  return labels[type]
}

export const getNodeColor = (type: NodeTypes): string => {
  const colors: Record<NodeTypes, string> = {
    data_source: '#0dc5c5',
    sma: '#FCD535',
    rsi: '#845ef7',
    atr: '#3a414a',
    ema: '#d65db1',
    compare: '#0ecb81',
    and: '#66bb6a',
    or: '#ffca28',
    not: '#ef5350',
    order: '#f6465d',
    value: '#78909c',
    field: '#4db6ac',
    trend: '#ce93d8',
    ob_query: '#f48fb1',
    bollinger: '#81d4fa',
    macd: '#a5d6a7',
    price: '#ff8a65',
    ob_in_range: '#a1887f',
    ob_not_stale: '#90a4ae',
  }
  return colors[type]
}

export const getDefaultParams = (type: NodeTypes): Record<string, unknown> => {
  switch (type) {
    case 'data_source':
      return { symbol: '', timeframe: 'M15' }
    case 'sma':
    case 'rsi':
    case 'atr':
    case 'ema':
      return { period: 14 }
    case 'compare':
      return { operator: '>' }
    case 'and':
    case 'or':
    case 'not':
      return {}
    case 'order':
      return {
        side: 'buy',
        risk_percent: 1.0,
        sl_atr_multiplier: 1.5,
        tp_r_multiple: 2.0,
        atr_period: 14,
      }
    case 'value':
      return { value: '' }
    case 'field':
      return { field: 'close' }
    case 'trend':
      return {}
    case 'ob_query':
      return { side: 'both', min_score: 6 }
    case 'bollinger':
      return { period: 20, std_dev: 2.0 }
    case 'macd':
      return { fast: 12, slow: 26, signal: 9 }
    case 'price':
      return { value: 'mid' }
    case 'ob_in_range':
      return {}
    case 'ob_not_stale':
      return { max_age_candles: 20 }
    default:
      return {}
  }
}

export const createInitialNode = (
  type: NodeTypes,
  position: { x: number; y: number }
): Node => {
  return {
    id: `node_${Date.now()}`,
    type,
    position,
    data: {
      params: getDefaultParams(type),
      label: getNodeLabel(type),
      color: getNodeColor(type),
    },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    draggable: true,
    style: {
      width: type === 'order' ? 220 : 180,
    },
  }
}

export const getInputCount = (type: NodeTypes): number => {
  switch (type) {
    case 'data_source':
      return 0
    case 'sma':
    case 'rsi':
    case 'atr':
    case 'ema':
      return 0
    case 'compare':
      return 2
    case 'and':
      return 2
    case 'or':
      return 2
    case 'not':
      return 1
    case 'order':
      return 1
    case 'value':
    case 'ob_query':
    case 'bollinger':
    case 'macd':
    case 'price':
      return 0
    case 'field':
    case 'ob_not_stale':
      return 1
    case 'trend':
      return 3
    case 'ob_in_range':
      return 2
    default:
      return 0
  }
}

export const getOutputCount = (type: NodeTypes): number => {
  switch (type) {
    case 'data_source':
      return 1
    case 'sma':
    case 'rsi':
    case 'atr':
    case 'ema':
      return 1
    case 'compare':
      return 1
    case 'and':
      return 1
    case 'or':
      return 1
    case 'not':
      return 1
    case 'order':
      return 0
    case 'value':
    case 'field':
    case 'trend':
    case 'ob_query':
    case 'bollinger':
    case 'macd':
    case 'price':
    case 'ob_in_range':
    case 'ob_not_stale':
      return 1
    default:
      return 0
  }
}
