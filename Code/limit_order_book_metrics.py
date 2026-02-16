# imports 
import pandas as pd
import numpy as np
import math
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression 
from dataclasses import dataclass

# get total volume in books
def total_volume_at_level(lob_side, lob_levels):
    """gets total volume for selected levels"""
    return sum([lob_side[level] for level in lob_levels])

def get_imbalance(lob: dict, n_levels, volume_weighted_imbalance = False) -> dict:
    """gets the imbalance between n_levels in the book"""
    lob_d = lob['d']
    lob_s = dict(sorted(lob['s'].items(), reverse = True))
    assert len(lob_d) >= n_levels and len(lob_s) >= n_levels # check that enough levels in data for analysis

    def get_weighted_levels(lob_side):
        """the pipeline, calculates the weighted volume at each level for one side of the book"""
        side_weighted_level = 0
        side_levels = list(lob_side.keys())[:n_levels] # pre sorted
        total_volume = total_volume_at_level(lob_side, side_levels)
        for level in side_levels:
            order_volume_at_level = lob_side[level]
            volume_weight = 1
            if len(side_levels) > 1 and volume_weighted_imbalance:
                volume_weight = order_volume_at_level / total_volume 
            side_weighted_level += float(order_volume_at_level) * float(volume_weight)
        return side_weighted_level

    # loop through levels and get best bid and ask (dicts will have different keys)
    s_bid = get_weighted_levels(lob_d)
    s_ask = get_weighted_levels(lob_s)

    imbalance = (s_bid - s_ask) / (s_bid + s_ask) 

    return round(imbalance, 4)

# get imbalance across many levels
def imbalance_wrapper(book, w_volume: bool, max_levels) -> list:
    imbalances = []
    for n_levels in range(1, max_levels+1):
        imbalance = get_imbalance(book, n_levels, volume_weighted_imbalance = w_volume)
        imbalances.append(imbalance)
    
    return imbalances

# convexity
def lob_side_slope(lob_side: dict) -> list: 
    """regresses level volume on level"""
    levels = len(lob_side)
    x = range(0, levels) # slr, so one feature must be reshaped
    y = [math.log(volume) for volume in lob_side.values()] # log linear model  

    # pre process 
    x = np.array(x).reshape(-1, 1) # col vector
    y = np.array(y) # col vector 

    # fir slr 
    y_hat = LinearRegression(fit_intercept = True).fit(x, y)
    
    return y_hat.coef_

# get quantity percentiles in each book
@dataclass(init=True)
class book_snapshot_metrics():
    """add all functions to this class***"""
    l2_books: dict[int, dict[str: dict[int, int]]]
    l2_counts: dict[int, dict[str: dict[int, int]]]
        
    def q_percentile_per_book(self):
        """gets size percentiles from the l2 book"""
        
        def _q_percentiles(lob: dict[str: dict[int, int]]):
            all_q = list(lob['s'].values()) + list(lob['d'].values())
            _p = lambda qs, rank: np.percentile(qs, rank)
            _p25 = _p(all_q, 25)
            _p50 = _p(all_q, 50)
            _p99 = _p(all_q, 99)
            return [_p25, _p50, _p99]

        # loop all snapshots 
        n = len(self.l2_books)
        features = np.zeros(shape = (n, 3))
        for obv, (_, lob) in enumerate(self.l2_books.items()):
            features[obv-1, :] = _q_percentiles(lob) # append 
        
        return features 

    # function gets the minimum and maximum level side quantity across all snapshot books 
    def q_side(self): 
        """gets the min and max"""
        min_q, max_q = 1e3, 0
        for lob in self.l2_counts.values():
            min_q = min(min_q, min(lob['s'].values()), min(lob['d'].values()))
            max_q = max(max_q, max(lob['s'].values()), max(lob['d'].values()))
        return [min_q, max_q]
