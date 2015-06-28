__all__ = [

    "RouterKey",
    "RouterTable",
]

from collections import defaultdict, OrderedDict


def sanitize(dictn):
    """
    Make sure the given dictionary, and
    all nested dictionaries, are converted
    to a SchemaDict which has keys sorted
    alphabetically.
    """
    for key, value in dictn.items():
        if type(value) == dict:
            dictn[key] = sanitize(value)

    return SchemaDict(sorted(dictn.items(), key=lambda kv: kv[0]))


class SchemaDict(OrderedDict):
    """
    Override the __str__ implementation of OrderedDict
    so we can guarantee the format of the string we use
    for the RouterKey hash.
    """
    def __str__(self):
        return "[{schema}]".format(schema=",".join([str(kv) for kv in self.items()]))


class RouterKey(object):
    """
    This class is used to determine the
    callback for a given event.
    """
    def __init__(self, schema):
        """
        Save our event schema (this includes the event type).
        We convert the schema to an OrderedDict sorted alphabetically
        by key to ensure that we ALWAYS have the same order for a given schema.
        """
        self.schema = sanitize(schema)

    def __hash__(self):
        """
        This object needs to be hashable in order to be able to be a dictionary key.
        We XOR the hashes of the event type and schema members so we can have
        multiple keys for the same event type, but different required schema elements,
        and have them return different hashes.
        """
        return hash(str(self.schema))

    def __eq__(self, other):
        """
        Determine if this callback key is equal to another.
        Two callback keys are exactly equal if they are
        applicable to the same event type and have the
        exact same schema key/value pairs.
        """
        return self.schema == other.schema

    def __ne__(self, other):
        """
        Determine if this callback key is not equal to another.
        """
        return not self.__eq__(other)

    def __and__(self, other):
        """
        Determine if this callback key is a "subset" of another.
        By this we mean: does the other callback key match the event
        type of this callback key AND does the schema of the other callback
        key contain at least the key/value pairs from this callback key schema.
        We also can specify that we do not care about schema by leaving this
        parameter as an empty FrozenDict.
        """
        try:
            schema_comparison = [self.schema[field_name] == other.schema[field_name]
                                 for field_name in self.schema.keys()]

            match = all(schema_comparison)

        # In the case that this key is the super set, and not the subset, a KeyError
        # will be raised as the other object does not have all of our keys. Be sure to catch it!
        except KeyError:
            match = False

        return match

    def __repr__(self):
        """
        Useful representation of a RouterKey.
        """
        return "<RouterKey: {schema}>".format(schema=self.schema)


class RouterTable(object):
    """
    A table containing CallbackKeys to map certain
    requirements of received events to callbacks and futures.
    """
    def __init__(self):
        """
        Initialize our table as empty.
        We use a default dict to simplify the logic in
        add_callback and add_future: if key is not in the dict
        then we populate the bucket with a list so we can
        always just do a .append.
        """
        self.future_table = defaultdict(list)
        self.callback_table = defaultdict(list)

    def add_callback(self, key, callback):
        """
        Add a callback to the callback table.
        """
        self.callback_table[key].append(callback)

    def add_future(self, key, future):
        """
        Add a future to the future table.
        """
        self.future_table[key].append(future)

    def get_callbacks(self, key):
        """
        Get all callbacks which are relevant to the given key.
        """
        results = []

        for table_key in self.callback_table.keys():
            if table_key & key:
                results.append(self.callback_table[table_key])

        return results

    def get_futures(self, key):
        """
        Get all futures which are relevant to the given key.
        """
        results = []
        key_list = []

        for table_key in self.future_table.keys():
            if table_key & key:
                key_list.append(table_key)
                results.append(self.future_table[table_key])

        for table_key in key_list:
            self.future_table[table_key] = []
            del self.future_table[table_key]

        return results