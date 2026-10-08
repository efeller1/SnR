# Backtest report

Development period 1990-01-31 to 2021-09-30; in-sample to 2011-03-31, out-of-sample after. Holdout (2021-10-31 on) untouched.

## Component tests (§9.1)

2 of 33 signals with enough history pass the 12-month bar (IC >= 0.05, t >= 2.0, same sign out of sample). Failing components stay on the dashboard but should get zero weight.

| asset   | signal             |   ic_is |   t_is |   ic_oos | passes   |
|:--------|:-------------------|--------:|-------:|---------:|:---------|
| AU      | au_debt            |   0.278 |  1.704 |   -0.332 | False    |
| AU      | au_deficit         |   0.299 |  2.104 |   -0.522 | False    |
| AU      | au_gold_m2         |   0.535 |  4.671 |    0.541 | True     |
| AU      | au_interest        |   0.066 |  0.326 |    0.269 | False    |
| AU      | au_mom             |  -0.514 | -2.713 |    0.373 | False    |
| AU      | au_trend           |  -0.513 | -3.797 |    0.303 | False    |
| AU      | comp:MOM           |  -0.651 | -4.631 |    0.367 | False    |
| AU      | comp:REG           |  -0.177 | -1.261 |    0.14  | False    |
| AU      | comp:STR           |   0.274 |  1.614 |   -0.126 | False    |
| AU      | comp:VAL           |   0.535 |  4.671 |    0.304 | True     |
| AU      | composite          |  -0.314 | -1.464 |    0.429 | False    |
| EN      | comp:MOM           |  -0.255 | -0.926 |   -0.253 | False    |
| EN      | comp:REG           |   0.176 |  1.377 |   -0.058 | False    |
| EN      | en_rel_mom         |  -0.258 | -0.947 |   -0.288 | False    |
| EN      | en_wti_mom         |  -0.434 | -1.421 |   -0.197 | False    |
| EQ      | comp:MOM           |   0.372 |  2.274 |   -0.116 | False    |
| EQ      | comp:REG           |   0.017 |  0.124 |    0.047 | False    |
| EQ      | comp:STR           |   0.157 |  0.797 |   -0.259 | False    |
| EQ      | comp:VAL           |  -0.178 | -0.96  |    0.325 | False    |
| EQ      | composite          |   0.121 |  0.656 |    0.123 | False    |
| EQ      | eq_cape            |  -0.178 | -0.96  |    0.325 | False    |
| EQ      | eq_mom             |   0.332 |  1.933 |   -0.132 | False    |
| EQ      | eq_productivity    |  -0.312 | -1.84  |    0.21  | False    |
| EQ      | eq_profit_share    |   0.331 |  2.046 |   -0.079 | False    |
| EQ      | eq_real_eps_growth |   0.102 |  0.48  |   -0.512 | False    |
| EQ      | eq_trend           |   0.34  |  2.159 |   -0.058 | False    |
| LTB     | comp:MOM           |  -0.419 | -3.996 |   -0.346 | False    |
| LTB     | comp:STR           |   0.06  |  0.423 |   -0.029 | False    |
| LTB     | composite          |  -0.261 | -2.073 |   -0.049 | False    |
| LTB     | ltb_debt           |   0.071 |  0.529 |    0.337 | False    |
| LTB     | ltb_interest       |   0.115 |  0.754 |   -0.114 | False    |
| LTB     | ltb_mom            |  -0.419 | -3.996 |   -0.346 | False    |
| USD     | comp:REG           |   0.078 |  0.384 |   -0.219 | False    |

## Regime tests (§9.2)

Empirical regime-fit scores (rank of each asset's annualized return across quadrants, mapped to 1-5) next to the priors. Few true regime changes exist, so treat this as directional.

Empirical:

| regime            |   AU |   BTC |   EN |   EQ |   USD |
|:------------------|-----:|------:|-----:|-----:|------:|
| goldilocks        |  2.3 |   2.3 |  2.3 |  3.7 |   3.7 |
| reflation         |  1   |   5   |  5   |  5   |   1   |
| stagflation       |  5   |   3.7 |  3.7 |  1   |   5   |
| deflationary_bust |  3.7 |   1   |  1   |  2.3 |   2.3 |

Prior:

|                   |   EQ |   AU |   BTC |   EN |   USD |
|:------------------|-----:|-----:|------:|-----:|------:|
| goldilocks        |    5 |    2 |     4 |    3 |     2 |
| reflation         |    4 |    4 |     4 |    5 |     2 |
| stagflation       |    1 |    5 |     2 |    4 |     3 |
| deflationary_bust |    2 |    3 |     1 |    1 |     5 |

## Portfolio tests (§9.3)

Monthly rebalancing, 10 bps per unit of turnover.

|              |   cagr |   vol |   sharpe |   max_drawdown |   turnover |
|:-------------|-------:|------:|---------:|---------------:|-----------:|
| model        |  0.083 | 0.081 |    0.703 |         -0.26  |      0.448 |
| equal_weight |  0.099 | 0.113 |    0.661 |         -0.229 |      0.389 |
| base_weights |  0.082 | 0.081 |    0.69  |         -0.256 |      0.303 |
| sixty_forty  |  0.076 | 0.088 |    0.586 |         -0.325 |      0.224 |
| sp500        |  0.11  | 0.146 |    0.613 |         -0.509 |      0.031 |

Model returns by regime:

| regime            |   months |   ann_return |   ann_vol |
|:------------------|---------:|-------------:|----------:|
| deflationary_bust |       89 |        0.055 |     0.086 |
| goldilocks        |       85 |        0.089 |     0.071 |
| reflation         |      126 |        0.109 |     0.089 |
| stagflation       |       81 |        0.068 |     0.074 |

## Ablation (§9.4, out of sample)

A component earns its place only if removing it lowers Sharpe or deepens the drawdown.

| case   |   sharpe |   max_drawdown |   d_sharpe |   d_max_drawdown | earns_place   |
|:-------|---------:|---------------:|-----------:|-----------------:|:--------------|
| full   |    1.025 |         -0.151 |      0     |            0     |               |
| -STR   |    1.028 |         -0.152 |      0.003 |           -0.001 | True          |
| -REG   |    1.016 |         -0.139 |     -0.009 |            0.012 | True          |
| -CAP   |    1.01  |         -0.149 |     -0.014 |            0.001 | True          |
| -VAL   |    1.037 |         -0.143 |      0.013 |            0.008 | False         |
| -LIQ   |    1.029 |         -0.15  |      0.004 |            0     | False         |
| -MOM   |    1.023 |         -0.141 |     -0.002 |            0.009 | True          |
| -L1    |    1.028 |         -0.152 |      0.003 |           -0.001 | True          |
| -L2    |    1.016 |         -0.139 |     -0.009 |            0.012 | True          |
| -L4    |    1.052 |         -0.154 |      0.028 |           -0.003 | True          |
| -L5    |    1.027 |         -0.153 |      0.002 |           -0.003 | True          |

## Control assets (§14, out of sample)

Controls scored below the premier average in 64% of months (bar: 70%). Score test passes: False. Return test passes: True.
