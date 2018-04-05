import json
import util
import location_utils

# Open the JSON file containing all restaurant information
_locations_json = 'locations.json'
with open(_locations_json, 'r') as fp:
    _locations = json.load(fp)

# Regex pattern for use in parser
_re_patt = r'(?P<location{}>.+)'

# Open the JSON file containing all sample utterances
_sample_utts = 'sample_utterances.json'
with open(_sample_utts, 'r') as fp:
    _samples = json.load(fp)

# Set all utterances to be regex patterns
for i in range(0, len(_samples)):
    _samples[i] = _samples[i].replace('{place}', _re_patt.format('')).replace('{place_two}', _re_patt.format('_two'))
#    _samples[i] = re.compile(reg_str)


def _existence(name):
    """
    This function checks if the location can be found on disk,
    if not return None.
    :param name: the name of the location
    :return: the data of the name if it exists, otherwise None
    """

    # Set the name to lowercase for easier matching
    name = name.lower()

    # First there is no match, which also is used as a default answer
    curr = None
    score = 0

    # Now go through all of our locations and find the best match
    for loc in _locations:
        location = _locations[loc]
        # We check with all aliases
        aliases = location['aliases']
        for al in aliases:
            # Here we use our _ratio_ function to look how closely these match
            temp = location_utils.ratio(al, name)
            # If the score is higher, change the candidate
            if temp > score:
                curr = location
                score = temp

    return curr


def address(event):
    """
    This function returns the address of the location the user asks for.
    :param event: the input event from Amazon Lex
    :return: the response depending on the input event
    """

    # First create the default response
    addr = "Sorry, I could not find an address for that location"

    # Extract the name and data
    name, data = _process_name(event)

    # Check if there exists any corresponding data
    if not data:
        return None

    # And finally check if this location has any address
    find_addr = data.get('address', None)
    if find_addr:
        return 'The address of {} is {}'.format(
            name, find_addr.capitalize())

    return addr


def open_hours(event):
    """
    Simple function for returning opening hours of buildings,
    if they have them.
    :param event: the input event from Amazon Lex
    :return: a response depending on if the corresponding hours could be found
    """

    # This is the default answer if no hours could be found
    hours = 'Sorry, I could not find any opening hours for this location'

    # Extract the name and data
    name, data = _process_name(event)

    # Check if there actually existed any data in the first place
    if not data:
        return None

    # And now check if the data includes any opening hours at all
    find_hours = data.get('opening_hours', None)
    if find_hours:
        return 'The opening hours for {} are the following: {}'.format(
            name, find_hours)

    return hours


def where_is(event):
    """
    This function is used for finding the relative direction of certain location, like smokki for example.
    The function treats the Alvarin Aukio as a center point of Otaniemi, and checks whether the given place is in the
    north side, west side, etc of Otaniemi
    """

    slots = find_slots(event)
    if not slots:
        return "Sorry, I could not find that place"

    # These are the coordinates of Alvarin aukio
    lat1, lon1 = 60.185739, 24.828786

    # Takes the latitude and longitude of the place given by user
    lat2, lon2 = slots[0]['lat'], slots[0]['lon']

    if not (lat2 and lon2):
        return "Sorry, I could not find where that is"

    # Takes the name of the place that user is looking for
    location_name = slots[0]['aliases'][-1]
    direction = location_utils.compass_point(lat1, lon1, lat2, lon2)
    distance = location_utils.distance(lat1, lon1, lat2, lon2)
    building = slots[0]['building']

    """
    Incase user asks 'where is reima', the answer is 'reima is in dipoli'
    this is more meaningful
    """
    if building:
        return "{} is in the {}".format(location_name, building)

    # In case the place is in a distance of less than 100 metres, it's concidered to be "in the middle area"
    if distance <= 100:
        return "{} is in the middle area of Otaniemi".format(location_name)

    return "{} is in the {} area of Otaniemi".format(location_name, direction)


def find_slots(event):
    """
    Goes trough value of every slot in input event, and incase the value of slot is other than null, it then
    checks whether there exists object for such value and if does, it appends the returned json objects into the array
    which is then returned at the end
    """

    slots = event['currentIntent']['slots']
    ret = []
    for slot in slots:
        if slots[slot]:
            slot_obj = _existence(slots[slot])
            if slot_obj:
                ret.append(slot_obj)

    if ret:
        return ret

    parsed = location_utils.parse_trans(event['inputTranscript'], _samples)
    existing_object = _existence(parsed)
    return [existing_object]


def direction_to(event):
    """
    Uses the information in event and tries to provide the user with info between the two points
    he or she has given to the libby
    """

    def helper(trans):
        """
        Little helper function to check whether user wants to get 'from a to b'
        or 'to a from b'
        """
        word_array = reversed(trans.split(" "))
        ordering = 0
        for word in word_array:
            if word.lower() == "to":
                ordering = 1
                break
            if word.lower() == "from":
                ordering = -1
                break

        return ordering

    user_input = event['inputTranscript']
    slot_values = find_slots(event)

    if len(slot_values) <= 1:
        return "Sorry, I could not find directions with these instructions"

    lat1, lon1 = slot_values[0]['lat'], slot_values[0]['lon']
    lat2, lon2 = slot_values[1]['lat'], slot_values[1]['lon']

    first_place, second_place = slot_values[0]['aliases'][-1], slot_values[1]['aliases'][-1]

    if not ((lat1 and lon1) and (lat2 and lon2)):
        return "Sorry I could not route from {} to {}".format(first_place, second_place)

    order = helper(user_input)
    distance = location_utils.distance(lat1, lon1, lat2, lon2)

    if first_place == slot_values[1]['building']:
        return "{} is in {}".format(second_place, first_place)
    if second_place == slot_values[0]['building']:
        return "{} is in {}".format(first_place, second_place)

    if order == -1:
        direction = location_utils.compass_point(lat1, lon1, lat2, lon2)
        return "{} is {} metres {} from {}".format(second_place, distance, direction, first_place)
    else:
        direction = location_utils.compass_point(lat1, lon1, lat2, lon2)
        return "{} is {} metres {} from {}".format(first_place, distance, direction, second_place)


def info(event):
    """
    This function returns general information about the location.
    It extracts the _info_ slot from the JSON file containing all locations,
    if such exists.
    :param event: the input event from Aamzon Lex
    :return: info about the location, if such exists
    """

    # Extract the name and data
    name, data = _process_name(event)

    resp = 'Unfortunately I am not able to find any information about {}' \
           ' but try to ask me something else about it'.format(name)

    # If there is no data, then there is no location,
    # so we tell this to the user
    if not data:
        return "Unfortunately I do not know such a location as {}".format(name)

    return data.get('info', resp)

#    # Else we try to extract the information
#    find_info = data.get('info', None)
#
#    # If there is prepared information about the location,
#    # we tell this to the user
#    if find_info:
#        return find_info
#
#    return 'Unfortunately I am not able to find any information about {}' \
#           ' but try to ask me something else about it'.format(name)


def _return_name(event):
    """
    This function simply returns the name of the location found in the query,
    if it exists.
    If the slot does not exist the function simply returns None.
    :param event: the input event from Amazon Lex
    :return: the slot value if it exists, otherwise None
    """

    # Extract the _slots_ from the input event
    slots = event['currentIntent']['slots']
    val = None

    # This for-loop just checks wether the slot exists
    for slot in slots:
        temp = slots[slot]
        if temp:
            val = temp

    return val


def _checker(trans, place, place_two):
    """
    This function finds the correct function for the answer.
    E.g. if the query of the user contains address the query is routed to the
    'address' function that finds the address.
    :param trans: the inputTranscript from the input data from Amazon Lex
    :return: the function dependent on the inputTranscript
    """

    trans = trans.replace(place, '').replace(place_two, '')

    def helper(strings):
        """
        Helper function for checking if a any from list of strings are
        contained in the inputTranscript.
        :param strings: a list of strings that correspond to a certain function
        :return: a boolean value if any elements exist in the string
        """
        for st in strings:
            if st in trans:
                return True
        return False

    # Create a list with strings that should lead to the address function
    # being used
    address_str = ['address', 'location']

    if helper(address_str):
        return address
    if 'open' in trans.replace(place, ''):#'open' in trans and 'open' in place:
        return open_hours
    if 'where is' in trans:
        return where_is
    if 'from' in trans and 'to' in trans:
        return direction_to
    return info


def _process_name(event):
    """
    Helper function for some of the functions above.
    It first checks if data can be found from the input slot value of the event,
    if it cannot it will give it to the parser to check if we can manually
    extract the location's name.
    After this it tries to extract the data that we have for the location, by
    help from the __existence_ function defined above.
    :param event: the input event from Amazon Lex
    :return: both the name and corresponding data
    """

    # First check if we can find the name through the slot value
    name = _return_name(event)
    # If not, check with the parser
    name = name if name else location_utils.parse_trans(event['inputTranscript'].lower(), _samples)
    # And then try to extract the data from our local JSON file
    data = _existence(name)

    # And return both the name (for future referencing) along with its data
    return name, data


def location_handler(event):
    """
    This is the handler function for the Location intent.
    :param event: the input event (data) received from AWS Lex
    :return: and ElicitIntent reponse
    """

    # Extract the inputTranscript from the input event
    trans = event['inputTranscript']
    # Also extract the slot value, in case we have to check for something in it
    place = event['currentIntent']['slots'].get('place', '')
    place_two = event['currentIntent']['slots'].get('place_two', '')
    if not place:
        place = ''
    if not place_two:
        place_two = ''
    # And send it to the checker to find the right function for handling
    func = _checker(trans, place, place_two)

    # Save the response from the function
    ans = func(event)

    # Default answer if all failed
    if not ans:
        ans = "Unfortunately I can't seem to find the location"

    return util.elicit_intent({}, ans)
