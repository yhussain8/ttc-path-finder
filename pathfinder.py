import pandas as pd
from datetime import timedelta as td

schedule = pd.read_feather('data/model/schedule.ftr')
stop_times = pd.read_feather('data/model/stop_times.ftr')
trips = pd.read_feather('data/model/trips.ftr')
stops = pd.read_feather('data/model/stops.ftr')

def find_closest_stop_id(input_lat, input_lon):
    stop_distance = stops.loc[:, ['stop_id', 'stop_lat', 'stop_lon']]
    stop_distance['distance'] = ( abs(input_lat - stop_distance['stop_lat'])**2 + abs(input_lon - stop_distance['stop_lon'])**2 )**(1/2)
    closest_stop_id = stop_distance.sort_values(by = 'distance').stop_id.iloc[0]
    return closest_stop_id

def find_closest_stops(input_lat, input_lon):
    stop_distance = stops.loc[:, ['stop_id', 'stop_lat', 'stop_lon']]
    stop_distance['distance'] = ( abs(input_lat - stop_distance['stop_lat'])**2 + abs(input_lon - stop_distance['stop_lon'])**2 )**(1/2)
    stop_distance = stop_distance.sort_values(by = 'distance').reset_index(drop = True)
    return stop_distance

def walking_speed_estimate():
    stop_id_A = 917
    stop_id_B = 9946
    time_in_minutes = 20
    stop_A_lat = stops.loc[stops.stop_id == stop_id_A, 'stop_lat'].values[0]
    stop_A_lon = stops.loc[stops.stop_id == stop_id_A, 'stop_lon'].values[0]
    stop_B_lat = stops.loc[stops.stop_id == stop_id_B, 'stop_lat'].values[0]
    stop_B_lon = stops.loc[stops.stop_id == stop_id_B, 'stop_lon'].values[0]
    distance = abs(stop_B_lat - stop_A_lat) + abs(stop_B_lon - stop_A_lon)
    walking_speed_in_seconds = distance / (time_in_minutes * 60)
    return walking_speed_in_seconds

def build_shortest_path_table(start_stop_id, current_time_delta):
    start_stop_lat = stops.loc[stops.stop_id == start_stop_id, 'stop_lat'].values[0]
    start_stop_lon = stops.loc[stops.stop_id == start_stop_id, 'stop_lon'].values[0]
    shortest_path = stops.copy()
    walking_distance = abs(shortest_path['stop_lat'] - start_stop_lat) + abs(shortest_path['stop_lon'] - start_stop_lon)
    walking_speed = walking_speed_estimate()
    walking_time = round(walking_distance / walking_speed, 0)
    shortest_path['arrival_time_delta'] = current_time_delta + pd.to_timedelta(walking_time, 'seconds')
    shortest_path = shortest_path.sort_values(by = 'arrival_time_delta').reset_index(drop = True)
    shortest_path['previous_stop'] = start_stop_id
    shortest_path['previous_mode'] = 'W'
    shortest_path['trip_id'] = None
    shortest_path['visited'] = False
    return shortest_path

def build_stop_schedule(start_stop_id, current_time_delta):
    stop_schedule = schedule.copy()
    stop_schedule = stop_schedule.loc[stop_schedule.stop_id == start_stop_id]
    stop_schedule['next_day'] = False
    stop_schedule.loc[stop_schedule.stop_time_delta < current_time_delta, 'next_day'] = True
    stop_schedule.loc[stop_schedule.stop_time_delta < current_time_delta, 'stop_time_delta'] = stop_schedule.loc[stop_schedule.stop_time_delta < current_time_delta, 'stop_time_delta'] + td(days = 1)
    stop_schedule = stop_schedule.sort_values(by = 'stop_time_delta').reset_index(drop = True)
    stop_schedule = stop_schedule.drop_duplicates(subset = 'shape_id', keep = 'first', ignore_index = True)
    return stop_schedule

def update_shortest_path(shortest_path, stop_schedule, current_time_delta, visiting_stop_id):
    
    upcoming_trip_stops = []
    for i in range(0, len(stop_schedule)):
        current_trip_id = stop_schedule.loc[i, 'trip_id']
        current_stop_sequence = stop_schedule.loc[i, 'stop_sequence']
        next_day = stop_schedule.loc[i, 'next_day']
        next_stops = schedule.loc[(schedule.trip_id == current_trip_id) & (schedule.stop_sequence > current_stop_sequence)].copy()
        if (next_day):
            next_stops.stop_time_delta = next_stops.stop_time_delta + td(days = 1)        
        upcoming_trip_stops.append(next_stops)
    upcoming_trip_stops = pd.concat(upcoming_trip_stops)
    upcoming_trip_stops = upcoming_trip_stops.sort_values(by = 'stop_time_delta').drop_duplicates(subset = 'stop_id', keep = 'first').reset_index(drop = True)
    
    for i in range(0, len(upcoming_trip_stops)):
        current_stop_id = upcoming_trip_stops.loc[i, 'stop_id']
        current_stop_time_delta = upcoming_trip_stops.loc[i, 'stop_time_delta']
        current_trip_id = upcoming_trip_stops.loc[i, 'trip_id']
        current_arrival_time = shortest_path.loc[shortest_path.stop_id == current_stop_id, 'arrival_time_delta'].values[0]
        
        if (current_arrival_time > current_stop_time_delta):
            shortest_path.loc[shortest_path.stop_id == current_stop_id, 'arrival_time_delta'] = current_stop_time_delta
            shortest_path.loc[shortest_path.stop_id == current_stop_id, 'previous_stop'] = visiting_stop_id
            shortest_path.loc[shortest_path.stop_id == current_stop_id, 'previous_mode'] = 'T'
            shortest_path.loc[shortest_path.stop_id == current_stop_id, 'trip_id'] = current_trip_id
            
    shortest_path = shortest_path.sort_values(by = 'arrival_time_delta').reset_index(drop = True)
    shortest_path.loc[shortest_path.stop_id == visiting_stop_id, 'visited'] = True
    
    return shortest_path

def update_walking_path(shortest_path, current_time_delta, visiting_stop_id):
    visiting_stop_lat = stops.loc[stops.stop_id == visiting_stop_id, 'stop_lat'].values[0]
    visiting_stop_lon = stops.loc[stops.stop_id == visiting_stop_id, 'stop_lon'].values[0]
    walking_distance = abs(shortest_path['stop_lat'] - visiting_stop_lat) + abs(shortest_path['stop_lon'] - visiting_stop_lon)
    walking_speed = walking_speed_estimate()
    walking_time = round(walking_distance / walking_speed, 0)
    shortest_path['walking_arrival_time_delta'] = current_time_delta + pd.to_timedelta(walking_time, 'seconds')
    
    mask = shortest_path.arrival_time_delta > shortest_path.walking_arrival_time_delta
    shortest_path.loc[mask, 'arrival_time_delta'] = shortest_path.loc[mask, 'walking_arrival_time_delta']
    shortest_path.loc[mask, 'previous_stop'] = visiting_stop_id
    shortest_path.loc[mask, 'previous_mode'] = 'W'
    shortest_path.loc[mask, 'trip_id'] = None
        
    
#     for i in range(0, len(shortest_path)):
        
#         arrival_time_delta = shortest_path.loc[i, 'arrival_time_delta']
#         walking_arrival_time_delta = shortest_path.loc[i, 'walking_arrival_time_delta']
#         if (arrival_time_delta > walking_arrival_time_delta):
#             shortest_path.loc[i, 'arrival_time_delta'] = walking_arrival_time_delta
#             shortest_path.loc[i, 'previous_stop'] = visiting_stop_id
#             shortest_path.loc[i, 'previous_mode'] = 'W'
#             shortest_path.loc[i, 'trip_id'] = None

    
    shortest_path = shortest_path.sort_values(by = 'arrival_time_delta').reset_index(drop = True)
    shortest_path = shortest_path.drop(columns = 'walking_arrival_time_delta')
    
    return shortest_path

def find_shortest_path(start_lat, start_lon, end_lat, end_lon, start_time_delta):
    start_stop_id = find_closest_stop_id(start_lat, start_lon)
    shortest_path = build_shortest_path_table(start_stop_id, start_time_delta)
    
    for i in range(0, len(shortest_path)):
               
        if (i < 940):
            pass
        else:
            break
        
        next_stop_record = shortest_path.loc[shortest_path.visited == False].iloc[0]
        current_stop_id = next_stop_record.stop_id
        current_time_delta = next_stop_record.arrival_time_delta
        previous_mode = next_stop_record.previous_mode
        
        print(i, current_stop_id, current_time_delta, previous_mode)
        
        if (previous_mode == 'T'):
            shortest_path = update_walking_path(shortest_path, current_time_delta, current_stop_id)
            pass
            # insert logic for calculating walking time to other stops
            # update shortest_path if walking time < current arrival time
        stop_schedule = build_stop_schedule(current_stop_id, current_time_delta)
        shortest_path = update_shortest_path(shortest_path, stop_schedule, current_time_delta, current_stop_id)
    
    return shortest_path

home = [43.76008911645013, -79.33181124795766]
longos = [43.75447805630398, -79.35689569243047]
gonoe = [43.7459232592541, -79.34612864369309]
current_time_delta = td(hours = 19, minutes = 0, seconds = 0)

output = find_shortest_path(home[0], home[1], longos[0], longos[1], current_time_delta)

print(output.head(5))