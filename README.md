# Limex Quantum Project: Probabilistic Modelling of the Limit Order Book (LOB)

This repository contains the all the code used to generate results in the paper 'Limex Quantum Project: Probabilistic Modelling of the Limit Order Book' (with the exception of the ```~/lob_animation.gif``` which is not referenced in the research paper). 

## Repository Strcuture

```text 
  LIMEX_PROJECT/
  ├── code/
  │   ├── mbo_schema_to_dataframe.py   # Load .dbn file into a DataFrame
  │   ├── build_limit_order_book.py    # Reconstruct LOB tick-by-tick (L2/L3)
  │   ├── limit_order_book_metrics.py  # Imbalance, slope, snapshot quantiles
  │   ├── probability_model.py         # Poisson arrivals + Pareto trade sizes
  │   ├── high_frequency_returns.py    # Equity curve & strategy backtest 
  │   └── lob_graphics.py              # Visualisations
  ├── notebooks/
  │   └── backtest.ipynb               # End-to-end pipeline & strategy analysis
  ├── paper/
  │   └── Limex_Quantum_Project.pdf    # Full research write-up
  ├── results/
  │   └── animated_figures/
  │       └── lob_animation.gif[]        # LOB depth animation
  └── README.md
```

## Data

The dataset for this repository has been omitted as it exceeds GitHub's 100MB hard limit. For reproducibility the dataset for this repository can be accessed via the following link. When running the ```backtest.ipynb``` notebook, make sure to change the data path to the path where you have downloaded the dataset to.

- https://drive.google.com/drive/folders/1vjTHirK7SBLCcwRH1mhoTtH74osyZoo8?usp=sharing

