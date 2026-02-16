import math
import numpy as np 
import pandas as pd
from sklearn.linear_model import LinearRegression
from sortedcontainers import SortedDict

class probability_model(): 
    # change a-b to s-d 
    def __init__(self, mbo_schema: pd.DataFrame, lob_snaps, lob_snaps_orders, time_unit: str, q_min: int = 1): 
        self.mbo_schemma: pd.DataFrame = mbo_schema
        self.lob_snaps: dict[int, dict[str, dict[int, int]]] = lob_snaps # dictionary of lobs with price and volume at level
        self.lob_snaps_orders: dict[int: dict[str, dict[int: int]]] = lob_snaps_orders # dictionary of lobs with prive and ordes at level
        self.q_min: int = q_min # min order size that defines power series)
        self.alpha: float = self._alpha_mle() 
        self.t = int(time_unit)*len(self.lob_snaps_orders)
        self.frequnecy_ask_trades = self._total(side = 's', snapshot_dict = lob_snaps_orders) / self.t
        self.frequnecy_bid_trades = self._total(side = 'd', snapshot_dict = lob_snaps_orders) / self.t

    def poisson_model(self, k_events: int, side: str = 'a') -> float:
        """
        simulates possion distrbution for number of trades within a time interval, over all snapshot books.
        models bid and ask trade events as independent poisson processes 
        """
        lambda_side = self.frequnecy_ask_trades
        if side == 'b':
            lambda_side = self.frequnecy_bid_trades
        return self._poisson_pdf(lambda_i = lambda_side, k_events=k_events)

    def power_series_pdf(self, q: float):
        """computes power series distribution of trade size, probability denisty of value, not probability of observing q"""
        if q < self.q_min:
            raise ValueError('q is not defined in domain, must choose q >= q_min')
        alpha = self.alpha
        return alpha * self.q_min**alpha * q**(-1 - alpha)

    def power_series_cdf(self, q: float):
        """
        computes the probability of price change being greater than x, this is equivalent to probability incoming trade size is greater than or equal 
        to scaled quantity value. 
        q: float = incoming trade size
        """
        alpha = self.alpha
        return 1 - (self.q_min / q)**alpha 
    
    def lambda_trade_intensity(self, lob :dict[str: dict[int, int]], traders_per_t_side: int, v_custom = None, side: str = 's'):
        """
        The expected number of trades that clear our quote on the first level
        - function designed to be used itervley over lob snapshot iterable
        """
        v = self._volume_first_level(lob_sz = lob, side = side) # volume in first level of book
        if v_custom is not None:
            v = v_custom
        Q_geq_v = 1 - self.power_series_cdf(q = v) # trade size follows a power series 
        return traders_per_t_side*Q_geq_v # number of trades greater than volume V follows a poisson distribution (probability of observing K quote clearing trades follows a poisson)
    
    def exponential_cdf(self, trade_intenisty: float, delta_t: int):
        """
        Used to get probability of waiting delta t time before aobserving a quote clearing trade on any side of the book.
        This function makes the assumption that the time between the number of quote clearning trades in unit time t is poisson distributed (that is 
        the time between each quote clearing trade is exponentialy distributed).
        
        trade_intenisty: float = number of quote clearning trades in unit time
        """
        return 1 - math.exp(-trade_intenisty*delta_t)

    # ------ helpers ------
    def _poisson_pdf(self, lambda_i: int, k_events = 1, t: int = 1):
        return ((lambda_i*t)**k_events * math.exp(-lambda_i*t)) / math.factorial(k_events)

    def _total(self, side, snapshot_dict):
        """gets the total values sum across a lob(s)"""
        return sum(
            sum(snapshot_dict[snap][side].values()) for snap in snapshot_dict
            )

    def _alpha_mle(self):
        """
        MLE for Pareto(order size >= q_min)
        this is number of orders over sum of logged order size over min num of orders 
        """
        size = self.mbo_schemma.loc[:, 'size'].to_numpy()
        sum_log_q = np.sum(np.log(size))
        n = size.shape[0]

        return n / (sum_log_q - n*np.log(self.q_min))
    
    def _volume_first_level(self, lob_sz: dict[str: dict[int, int]], side: str):
        """gets volume in the first level"""
        lob_i = SortedDict(lob_sz[side])
        if side == 'd':
            return lob_i.peekitem(-1)[0] # greatest value is TOB 
        return lob_i.peekitem(0)[0] # least value is TOB 
    
    def _queue_volume(self):


        pass
    
    # OMITTED used for price impact model (omitted due to noisy prices)
    def _delta_p_model(self, delta_p: np.ndarray, Q: np.ndarray): # this is a quantile regression Q_i(log(delta p) | Q) = log(K) + beta_i Q_i,j + e_j
        """
        estimates constant of proportonality k and beta term by transforming equality to least squares problem
        the intercept and quantity coefficient give the value of k and beta respectivley. 
        delta p = kQ^b <=> log(deltap) = log(k) + b*log(Q) + e_i
        """
        if Q.ndim == 1:
            Q.reshape(-1, 1) # to column vector 

        Q = np.log(Q) 
        delta_p = np.log(delta_p)

        delta_p_hat = LinearRegression(fit_intercept = False).fit(Q, delta_p)

        return [delta_p_hat.intercept_, delta_p_hat.coef_]
    
        
        

    