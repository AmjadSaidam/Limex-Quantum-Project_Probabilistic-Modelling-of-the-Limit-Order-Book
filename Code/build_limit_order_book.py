# class and type casting
from __future__ import annotations
from dataclasses import dataclass, field # for slot class and customise how attributed are used in class
from collections import defaultdict
from itertools import takewhile 
from sortedcontainers import SortedDict # so dicts have insertion and key sorting (default ascending sort)
# time
import datetime # for time based snapshots 
# api  
import databento as db 
# general 
import pandas as pd 
import numpy as np 
from copy import deepcopy # so applending same list of dict does not update when dict is updated 
from attr import attrs

#------- Metadata -------
@dataclass(init = True, slots = True)
class PriceLevel:
    """slot type class that pulls data from MBO schema"""
    price: int 
    size: int 
    count: int = 0 

    def __str__(self) -> str: 
        price = self.price / db.FIXED_PRICE_SCALE
        return f"{self.size:4} @ {price:6.2f} | {self.count:2} order(s)"

#------- construct level -------
@dataclass(init = True, slots = True)
class LevelOrders: 
    """takes price and list of individual orders (order = db.MBOMsg)"""
    price: int 
    orders: list[db.MBOMSg] = field(default_factory = list, compare = False) # field ensures that updates to attributes shared by insentiatiosn of the class are not all mutated on attribute assigenment

    def __bool__(self) -> bool: 
        return bool(self.orders)
    
    @property # access function as an attribute 
    def level(self) -> PriceLevel: 
        """returns price, size, number of orders for a given level, this is L3->L2 aggregation"""
        return PriceLevel(
            price = self.price, 
            size = sum(o.size for o in self.orders), 
            count = sum(1 for o in self.orders if not o.flags & db.RecordFlags.F_TOB) # ensure that order message does not require book side to be cleared 
        )
    
#------- Type Transformation -------
@dataclass(init = True, slots=True)
class pandas_to_MBOMsg():
    Index: pd.DatetimeIndex
    side: str
    order_id: int
    action: str 
    price: int 
    size: int
    flags: str 

#------- LOB Builder Function -------
@dataclass(slots = True)
class Book: 
    """helper class used to build LOB from MBO schema"""
    # define sorted asks and bids dicts, where each order is a level level orders object allowing for quick data retrival (these are )
    orders_by_id: dict[int: db.MBOMsg] = field(default_factory = dict)
    asks: SortedDict[int, LevelOrders] = field(default_factory = SortedDict)
    bids: SortedDict[int, LevelOrders] = field(default_factory = SortedDict)

    def bbo(self) -> tuple[PriceLevel | None, PriceLevel | None]: # returns tuple of multi type
        """returns best bid and best ask"""
        return self.get_bid_level(), self.get_ask_level()
     
    def get_bid_level(self, idx: int = 0) -> PriceLevel | None: 
        """for given depth in book will return idx best bid, top down (descending)"""
        if self.bids and len(self.bids) > idx:
            return self.bids.peekitem(-(idx + 1))[1].level 

    def get_ask_level(self, idx: int = 0) -> PriceLevel | None:
        """for given depth in book will return idx best ask, bottom up (ascending)"""
        if self.asks and len(self.asks) > idx: 
            return self.asks.peekitem(idx)[1].level # get value from start of dict (lowest up)
        
    def get_bid_level_by_px(self, px: int) -> PriceLevel | None:
        """for given bid price will return bid level, L2 snapshot"""
        try:
            return self._get_level(px, 'B').level # lookup price, and return PriveLevel, a class with attributes price, size and count 
        except KeyError: 
            return None
    
    def get_ask_level_by_px(self, px: int) -> PriceLevel | None: 
        """fro given ask price will return ask level, L2 snapshot"""
        try: 
            return self._get_level(px, 'A').level
        except KeyError:
            return None
        
    def get_order(self, id: int) -> db.MBOMSg | None: 
        """gets an order by id"""
        return self.orders_by_id.get(id) # lookup dict value
    
    def get_queue_pos(self, id: int) -> int | None:
        """gets order by id, then gets order level and computes the size of order less than that level to determine queue position"""
        order = self.get_order(id)
        if not order: # if None return None 
            return None
        level = self._get_level(order.price, order.side)
        return sum(
            order.size for order in takewhile(lambda o: o.order_id != id, iterable = level.orders) # sum over list of orders with queue priority 
        )
    
    def get_snapshot(self, level_count: int = 1) -> list[db.BidAskPair]:
        """for given book depth will populate the db.BidAskPair container, with price, size and number of orders depending on if the order is a bid/ask and if level exists"""
        snapshots = [] # L2 data bid and ask snapshots [ba_pair1, .... ]
        for level in range(level_count): 
            ba_pair = db.BidAskPair() # aggragted level view 
            
            bid = self.get_bid_level(level) # get L2 bid data at level
            if bid: 
                ba_pair.bid_px = bid.price
                ba_pair.bid_sz = bid.size 
                ba_pair.bid_ct = bid.count

            ask = self.get_ask_level(level) # get L2 ask data at level
            if ask: 
                ba_pair.ask_px = ask.price 
                ba_pair.ask_sz = ask.size
                ba_pair.ask_ct = ask.count
            
            snapshots.append(ba_pair) # appends the L2 view for bid and ask at level, to snapshots
        return snapshots

    def apply(self, mbo: db.MBOMSg) -> None: 
        """deals with all order actions, _ prefix defines helper function"""
        # actions (T, F, N) do not affect the book, so skip
        if mbo.action in ('T', 'F', 'N'):
            return
        
        # acton R, clears the book 
        if mbo.action == 'R':
            self._clear()
            return 
        
        # side = N is only valid with T, F and C actions 
        assert mbo.side in ('A', 'B')
        
        # UNDED_PRICE flag indicates book level should be cleared
        if mbo.price == db.UNDEF_PRICE and mbo.flags & db.RecordFlags.F_TOB:
            self._side_levels(mbo.side).clear()
            return

        # A = new order 
        if mbo.action == 'A':
            self._add(mbo) 
        # C = partialy/fully cancel order size
        elif mbo.action == 'C': 
            self._cancel(mbo)
        # M = modify order
        elif mbo.action == 'M':
            self._modify(mbo)
        else: 
            raise ValueError(f'Unkown action={mbo.action}')
        
    #------- helper methods -------
    def _clear(self) -> None: 
        """clear dict attributes"""
        self.orders_by_id.clear()
        self.asks.clear()
        self.bids.clear()

    def _add(self, mbo: db.MBOMsg) -> None:
        """deals with add action, takes order and appends to level, and deals with flag cases"""
        if mbo.flags & db.RecordFlags.F_TOB: 
            levels = self._side_levels(mbo.side)
            levels.clear()
            levels[mbo.price] = LevelOrders(price = mbo.price, orders = [mbo])
        else:
            # if not false flag then check if order is new and append to level
            level = self._get_or_insert_level(mbo.price, mbo.side)

            assert mbo.order_id not in self.orders_by_id 
            
            self.orders_by_id[mbo.order_id] = mbo 
            level.orders.append(mbo)

    def _cancel(self, mbo: db.MBOMSg) -> None: 
        """deals with cancel action,"""
        order = self.orders_by_id[mbo.order_id]
        level = self._get_level(mbo.price, mbo.side)
        
        # order size at least as historical size 
        assert order.size >= mbo.size

        order.size -= mbo.size # change amount
        # incase of full cancel, remove order from side 
        if order.size == 0: 
            # if order now has 0 size, remove from book
            self.orders_by_id.pop(mbo.order_id) # delete order id from dict  
            level.orders.remove(order) # remove value from order list
            if not level: # if level empty remove from book 
                self._remove_level(mbo.price, mbo.side)

    def _modify(self, mbo: db.MBOMSg) -> None:
        """
        deals with M actions. gets order by id, if new side is equal to historic side will get level
        1. if price is different will remove from level
        2. if level is then empty will delete level from book
        3. then appends order to existing level, or cretaes a new level with that order
        4. if order historic size < new size, remove order from level and append again (dequeue order)
        5. otherwiase just adjsut size 
        """
        order = self.orders_by_id.get(mbo.order_id)
        if order is None: 
            self._add(mbo)
            return
        
        assert order.side == mbo.side, f'Order {order} changed side to {mbo.side}'
        
        level = self._get_level(order.price, order.side)
        
        if order.price != mbo.price: # price loss priority 
            level.orders.remove(order)
            if not level: # if level empty after deleting order 
                self._remove_level(order.price, mbo.side)
            level = self._get_or_insert_level(mbo.price, mbo.side)
            level.orders.append(mbo)

        elif order.size < mbo.size: # increase size, priority loss
            level.orders.remove(order)
            level.orders.append(mbo)

        else: # size changed, priority maintained
            level.orders[level.orders.index(order)] = mbo 
        self.orders_by_id[mbo.order_id] = mbo
        
    def _side_levels(self, side: str) -> SortedDict:
        """given side, will return bid or ask levels"""
        if side == 'A': 
            return self.asks
        if side == 'B': 
            return self.bids 
        raise ValueError(f'Invalid {side=}')

    def _get_level(self, price: int, side: str) -> LevelOrders: 
        """get price level from book"""
        levels = self._side_levels(side)
        if price not in levels: 
            raise KeyError(f'No price level found for {price=} ans {side=}')
        return levels[price]

    def _get_or_insert_level(self, price: int, side: str) -> LevelOrders:
        """given price and side, gets level, and and appends level information (price, size, count) to level (L2 aggregation)"""
        levels = self._side_levels(side)
        if price in levels: 
            return levels[price]
        level = LevelOrders(price = price)
        levels[price] = level
        return level
    
    def _remove_level(self, price: int, side: str) -> None: 
        """given price and side, gets bids or ask side of book and removes a given price"""
        levels = self._side_levels(side)
        levels.pop(price)

#------- Build LOB -------
def lob(mbo_schema: pd.DataFrame, snapshots = False, frequency = '1min') -> dict:
    """iterate over book update to build lob"""
    books: list[Book] = []
    snapshots_book: dict[int: dict[str, dict[int, int]]] = {}
    orders_at_level: dict[int: dict[str, dict[int: int]]] = {}
    micro_prices: list = []
    lob_t: list = []
    trade_fills: dict[str: list(int)] = {'T': [], 'F': []}
    
    # initialise book 
    market = Book()

    price_l2 = lambda side : {px: side[px].level.size for px in side.keys()}
    count_l2 = lambda side : {px: side[px].level.count for px in side.keys()}

    # track next snapshot
    if snapshots: 
        delta = pd.tseries.frequencies.to_offset(frequency)
        time_offset = mbo_schema.index[0] + delta

    lft_p = 0
    for idx, order in enumerate(
        mbo_schema.itertuples(index=True)
        ):
        market.apply(pandas_to_MBOMsg(
            Index = order.Index,
            side = order.side,
            order_id = order.order_id, 
            action = order.action, 
            price = int(order.price), 
            size = int(order.size),
            flags = order.flags
        ))

        # aggregate level by time
        if snapshots: 
            if order.Index >= time_offset: 
                
                # build lob 
                lob_snap = {'s': price_l2(market.asks), 'd': price_l2(market.bids)}
                snapshots_book[idx] = deepcopy(lob_snap) # deepcopy otherwise all snapshots point to same dict 

                # get microprice
                snapshot = market.get_snapshot(level_count = 1)[0] # list of db.BidAskPair object with PriceLevel attributes 
                micro_prices.append((snapshot.ask_px*snapshot.bid_sz + snapshot.bid_px*snapshot.ask_sz) / (snapshot.ask_sz + snapshot.bid_sz))

                # get min depth among book snapshot, calculate number of orders at each level in book snapshot
                orders = {'s': count_l2(market.asks), 'd': count_l2(market.bids)}
                orders_at_level[idx] = deepcopy(orders)

                # update time 
                lob_t.append(order.Index)
                books.append(deepcopy(market))
                time_offset += delta # increment time 

                # group by trades and fills
                data_snap = mbo_schema.iloc[lft_p:idx, :] # get data chunck
                key, label = 'action', 'size'
                data_group = data_snap.groupby(key).agg(
                    counts = (key, 'count'), 
                    sums = (label, 'sum') # subset size based on counts of each event
                ) # group size by action 
                ct_T = data_group.loc['T', 'counts'] if 'T' in data_group.index else 0 # counts of number of trades 
                sm_F = data_group.loc['F', 'sums'] if 'F' in data_group.index else 0 # total size of fill trades 
                # fill dicts
                trade_fills['T'].append(ct_T) 
                trade_fills['F'].append(sm_F)
                lft_p = idx 

    # build final lob (REMOVE AND RETURN JUST BOOK)
    asks = price_l2(market.asks)
    bids = price_l2(market.bids)
    lob = {'s': asks, 'd': bids}

    return {'book': books,
            'lob': lob, 
            'lob_snapshots': snapshots_book,
            'micro_price': micro_prices, 
            'lob_snapshot_order_count': orders_at_level, 
            'lob_snapshot_times': lob_t, 
            'trades_fills': trade_fills}