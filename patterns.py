import numpy as np
'''
x : Price list
y : Last comparible value.
z : Historic comparible value.

# find_high_high
( x : price list, y : last high, z : historic high value )
Return highest value seen vs both recent and historically or None.

# find_high
( x : price list, y : last high )
Return the highest value seen or None.

# find_low_high
( x : price list, y : last high, z : historic high value )
Return highest value seen recently but lower historically or None.

# find_low_low
( x : price list, y : last low, z : historic low value )
Return the lowest value seen vs both recent and historically or None.

# find_low
( x : price list, y : last low )
Return the lowest value seen or None.

# find_high_low
( x : price list, y : last low, z : historic low value )
Return lowest value seen recently but higher historically or None.
'''
## High setups
find_high_high  = lambda x, y, z: x.max() if z < x.max() > y else None
find_high       = lambda x, y: x.max() if x.max() > y else None
find_low_high   = lambda x, y, z: x.max() if z > x.max() > y else None
## Low setup
find_low_low    = lambda x, y, z: x.min() if z > x.min() < y else None
find_low        = lambda x, y: x.min() if x.min() < y else None
find_high_low   = lambda x, y, z: x.min() if z < x.min() < y else None

"""
Trading patterns.

"""
class pattern_W:
    def __init__(self):
        self.required_points = 4
        self.result_points = 1 # Only required for testing to view outcome.
        self.segment_span = 4
        self.price_point = 0

    def check_condition(self, point_set):
        if point_set[3] > point_set[1] > point_set[2] > point_set[0]:
            print('part 1')
            if point_set[1] > point_set[2]+((point_set[3]-point_set[2])/2) and (100 - ((point_set[0]/point_set[2])*100)) < 1.2:
                print('part 2')
                return(True)

        return(False)