from sortedcontainers import SortedDict
import numpy as np 
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# bet price 
def price_from_data(data, max_freq, axis):
    current_price = data.iloc[-1]
    avg_price = np.mean(data, axis = 0)
    percentile_25 = np.percentile(data, 25)
    percentile_75 = np.percentile(data, 75)
    iqr = percentile_75 - percentile_25
    top = percentile_75 + 1.5*iqr
    bottom = percentile_25 - 1.5*iqr
    axis.hlines(y = [bottom, percentile_25, percentile_75, top], xmin = 0, xmax = max_freq, color = ['yellow'], linestyles = ':', 
               label = 'Bottom Outliers | 25% percentile | 75th percentile | Top Outliers')
    axis.hlines(y = avg_price, xmin = 0, xmax = max_freq, color = 'blue', linestyle = '-', label = 'Average price')
    axis.hlines(y = current_price, xmin = 0, xmax = max_freq, color = 'purple', linestyle = '-', label = 'Current price')
    axis.legend()

def format_lob(lob_sid, bottom_book, top_book, side):
    if side == 'b':
        lob_sid = dict(sorted(lob_sid.items(), reverse = True)) # sort in descending order 

    # sort check 
    cv_side = {}
    cumsum = 0
    for price, volume in lob_sid.items():
        cumsum += volume 
        cv_side[price] = cumsum 

    local_lob = {}
    for key, value in cv_side.items():
        if key == min(max(key, bottom_book), top_book): # check key within book snapshot range (price range)
            local_lob[key] = value
    return local_lob

# function that gets side of OB 
def vis_lob_side(lob_sid: SortedDict, col, bottom_book, top_book, axis, side: str = ('b', 's')):
    """plots the number of order at each unique price, allowing us to see where most order sit, this does not tell us where most liquidity sits
    """
    lob = format_lob(lob_sid, bottom_book, top_book, side)
    axis.barh(y = lob.keys(), width = lob.values(), height = 0.2, color = col, alpha = 0.7)
    return lob
    
# animation function
def animate_lob(lob_snaps, x_min, x_max, **kwargs):
    fig, ax = plt.subplots()

    artists = []
    for lob in lob_snaps:
        container_b = vis_lob_side(lob, bottom_book = x_min, top_book = x_max, axis = ax, col = 'g', side = 'b')
        container_a = vis_lob_side(lob, bottom_book = x_min, top_book = x_max, axis = ax, col = 'r', side = 's')
        artists.append(container_a)
        artists.append(container_b)

    ani = animation.ArtistAnimation(fig = fig, artists = artists, **kwargs)
        
