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


def get_tops_bottoms(candles, segment_span, price_point):
    last_timestamp = 0
    read_complete = False
    data_points = []

    c_move, last_val = ('up', 0) if candles[0][1] > candles[segment_span][1] else ('down', 999999)
    set_start = 0

    while not(read_complete):
        set_offset = set_start+segment_span

        if set_offset < len(candles):
            set_end = set_offset
        else:
            set_end = len(candles)
            read_complete = True

        c_set = np.asarray(candles[set_start:set_end])

        if price_point == 0:
            val_index = 3 if c_move == 'down' else 2
        elif price_point == 1:
            val_index = 4
        elif price_point == 2:
            val_index = 1
        find_result = find_high(c_set[:,val_index], last_val) if c_move == 'up' else find_low(c_set[:,val_index], last_val)

        if find_result:
            # Used to find timestamp of new value.
            time_index = np.where(c_set[:,val_index] == find_result)[0][0]

            # Used for plotting.
            last_timestamp = c_set[time_index][0]
            last_val = find_result
            set_start += time_index+1
        else:
            # Record the value to be used later.
            data_points.append([int(last_timestamp), last_val])

            # Switch between up and down.
            c_move, last_val = ('up', 0) if c_move == 'down' else ('down', 999999)
    
    return(data_points[::-1])


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