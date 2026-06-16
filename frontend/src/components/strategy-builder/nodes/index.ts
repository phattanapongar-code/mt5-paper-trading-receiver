import DataSourceNode from './DataSourceNode'
import SMANode from './SMANode'
import RSINode from './RSINode'
import ATRNode from './ATRNode'
import EMANode from './EMANode'
import CompareNode from './CompareNode'
import LogicNode from './LogicNode'
import OrderNode from './OrderNode'

export const nodeTypes = {
  data_source: DataSourceNode,
  sma: SMANode,
  rsi: RSINode,
  atr: ATRNode,
  ema: EMANode,
  compare: CompareNode,
  and: LogicNode,
  or: LogicNode,
  not: LogicNode,
  order: OrderNode,
}
