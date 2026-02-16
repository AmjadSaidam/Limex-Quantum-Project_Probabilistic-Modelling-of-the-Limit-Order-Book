import pandas as pd 
import numpy as np 

def hft_returns(returns: np.ndarray, price: np.ndarray, position: pd.Series, princable_value: float = 1, dollar_fee: float = 0, bnh = False) -> dict: 
    """calculates the model returns given asset logged returns for retail traders and HFT firm, curve = Et = [E_t-1 * e^r_t*position] - fee"""
    past_pos = position.shift(1)
    position_change = (position - past_pos).fillna(0) # first value will always be change, incuring fee 

    # net equity
    equity = princable_value
    equity_net = []
    total_fees = 0
    total_volume = 0
    for t in range(len(returns)):
        if bnh: 
            equity *= np.exp(returns[t])
            equity_net.append(equity)
            continue

        equity *= np.exp(returns[t] * position[t]) # multplicative returns, sign adjusted 
        
        shares = equity / price[t]

        if position_change[t] != 0: 
            total_volume += equity
            fee = shares*dollar_fee*2 # sell (+fee) switch side (+fee)
            equity -= fee # adjusted equity, if fee is 0 then this is just equity
            total_fees += fee
            
        equity_net.append(equity)

    return {'equity': equity_net,
            'total_fees': round(total_fees, 8),
            'total_volume': total_volume, 
            'num_trades': int(
                sum(abs(np.sign(position_change)))
                )}