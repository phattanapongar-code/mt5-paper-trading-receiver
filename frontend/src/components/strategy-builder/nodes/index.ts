import DataSourceNode from './DataSourceNode'
import SMANode from './SMANode'
import RSINode from './RSINode'
import ATRNode from './ATRNode'
import EMANode from './EMANode'
import CompareNode from './CompareNode'
import LogicNode from './LogicNode'
import OrderNode from './OrderNode'
import ValueNode from './ValueNode'
import FieldNode from './FieldNode'
import TrendNode from './TrendNode'
import OBQueryNode from './OBQueryNode'
import BollingerNode from './BollingerNode'
import MACDNode from './MACDNode'
import PriceNode from './PriceNode'
import OBInRangeNode from './OBInRangeNode'
import OBNotStaleNode from './OBNotStaleNode'

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
  value: ValueNode,
  field: FieldNode,
  trend: TrendNode,
  ob_query: OBQueryNode,
  bollinger: BollingerNode,
  macd: MACDNode,
  price: PriceNode,
  ob_in_range: OBInRangeNode,
  ob_not_stale: OBNotStaleNode,
}
