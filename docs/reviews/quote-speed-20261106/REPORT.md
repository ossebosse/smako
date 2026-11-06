# Faster quoting for large store selections (2026-11-06)

Same release image (app-80627382c72d-76de7352); only basket_optimizer.py from branch quote-speed mounted over it. Isolated containers, no network, real price universes. Digest = stores, products, package counts and recipes.

## Base cases (20)
```
lund-3km-1             SAME PASS           174.33      46.7 ->    54.5 s
lund-3km-2             SAME PASS           168.37      62.2 ->    42.4 s
lund-3km-3             SAME PASS           166.57      62.2 ->    43.5 s
lund-3km-4             SAME PASS           166.57      63.3 ->    44.9 s
lund-3km-all           SAME PASS           166.57      65.8 ->    47.3 s
lund-kommun-1          SAME PASS           174.33      62.0 ->    43.0 s
lund-kommun-2          SAME PASS           168.37      80.3 ->    49.4 s
lund-kommun-3          SAME PASS           166.57      81.8 ->    53.3 s
lund-kommun-4          SAME PASS           166.57      78.2 ->    51.1 s
lund-kommun-all        SAME PASS           166.57      77.5 ->    50.3 s
malmö-3km-1            SAME PASS           171.73      67.1 ->    54.2 s
malmö-3km-2            SAME PASS           167.58      90.9 ->    59.0 s
malmö-3km-3            SAME PASS           166.52      95.6 ->    59.7 s
malmö-3km-4            SAME PASS           166.52      98.7 ->    62.3 s
malmö-3km-all          SAME PASS           166.52      96.5 ->    58.9 s
malmö-kommun-1         SAME PASS           171.73     178.2 ->    91.3 s
malmö-kommun-2         SAME PASS           162.95     236.4 ->   113.1 s
malmö-kommun-3         SAME PASS           161.5      244.4 ->   117.6 s
malmö-kommun-4         SAME PASS           161.5      237.9 ->   112.8 s
malmö-kommun-all       SAME PASS           161.5      226.7 ->   113.2 s
20/20 identical
```

## Meat-heavy, many ingredients (14)
```
lund-primer            SAME PASS           840.87      45.5 ->    43.2 s
lund18-A-3             SAME PASS           840.87      24.3 ->    21.2 s
lund18-A-all           SAME PASS           837.97      23.7 ->    21.2 s
lund32-A-3             SAME PASS           813.63      32.7 ->    28.4 s
lund32-A-all           SAME PASS           831.95      26.8 ->    23.3 s
lund32-B-3             SAME PolicyConflict None        16.5 ->    17.5 s
lund32-B-all           SAME PolicyConflict None        12.9 ->    12.9 s
malmö-primer           SAME PASS           845.57      43.2 ->    38.8 s
malmö31-A-3            SAME PASS           845.57      35.7 ->    30.4 s
malmö31-A-all          SAME PASS           793.36      37.7 ->    32.2 s
malmö57-A-3            SAME PASS           798.14      98.4 ->    65.6 s
malmö57-A-all          SAME PASS           783.2       82.1 ->    52.3 s
malmö31-B-3            SAME PolicyConflict None        24.3 ->    23.1 s
malmö31-B-all          SAME PolicyConflict None        20.1 ->    19.6 s
14/14 identical
```

Unit equivalence: tests/test_optimizer.py (shape vs full resolver, 400 random quantities) and tests/test_store_set_search.py (store winners vs full quote sets over 25 searches x 20 seeds).
