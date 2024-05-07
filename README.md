# Traffic-Assignment-2024

Codes in this repository compute the traffic assignment using the algorithms of:
- Frank-Wolfe Algorithm with Exact Line Search
- Frank-Wolfe Algorithm with step size of (2 / (k + 2))
- Conjugate Direction Frank-Wolfe Algorithm
- Path-based Projection Gradient Algorithm with Exact Line Search
- Path-based Projection Gradient Algorithm with fixed step size

You can see the performance:
![](gap_iteration)
![](gap_time)

You can see the references:
- Jayakrishnan R, Tsai WT, Prashker JN, Rajadhyaksha S, 1994 A faster path-based algorithm for traffic assignment. Transportation Research Record .
- LeBlanc LJ, Morlok EK, Pierskalla WP, 1975 An efficient approach to solving the road network equilibrium traffic assignment problem. Transportation research 9(5):309–318.
- Mitradjieva M, Lindberg PO, 2013 The stiff is moving—conjugate direction frank-wolfe methods with applications to traffic assignment. Transportation Science 47(2):280–293.

## Acknowledgments

 This work is based on [Traffic-Assignment-Frank-Wolfe-2021](https://github.com/matteobettini/Traffic-Assignment-Frank-Wolfe-2021). I focused on fixing this implementation and extending it to implement more algorithms.
