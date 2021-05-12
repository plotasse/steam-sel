# This is appinfo.py from steamfiles (https://github.com/leovp/steamfiles),
# with a few modifications to parse the file lazily as apps are requested.
import struct
from collections import namedtuple

__all__ = ('AppinfoLazyDecoder')

VDF_VERSIONS = [0x07564426, 0x07564427]
VDF_UNIVERSE = 0x00000001

LAST_SECTION = b'\x00'
LAST_APP = b'\x00\x00\x00\x00'
SECTION_END = b'\x08'

TYPE_SECTION = b'\x00'
TYPE_STRING = b'\x01'
TYPE_INT32 = b'\x02'
TYPE_INT64 = b'\x07'

# VDF has variable length integers (32-bit and 64-bit).
Integer = namedtuple('Integer', ('size', 'data'))

class AppinfoLazyDecoder:

    def __init__(self, data, wrapper=dict):
        self.wrapper = wrapper        # Wrapping container
        self.app_headers = {}         # AppID to parsed header
        self.app_offsets = {}         # AppID to memory offset
        self.data = memoryview(data)  # Incoming data (bytes)
        self.offset = 0               # Parsing offset

        # Commonly used structs
        self._read_int32 = self.make_custom_reader('<I', single_value=True)
        self._read_int64 = self.make_custom_reader('<Q', single_value=True)
        self.read_vdf_header = self.make_custom_reader('<2I')
        self.read_game_header = self.make_custom_reader('<3IQ20sI')
        self.size_game_header = struct.Struct('<3IQ20sI').size

        # Functions to parse different data structures.
        self.value_parsers = {
            0x00: self.parse_subsections,
            0x01: self.read_string,
            0x02: self.read_int32,
            0x07: self.read_int64,
        }

        self.build_app_offsets()

    def build_app_offsets(self):
        self.parsed = self.wrapper()

        # These should always be present.
        header_fields = ('version', 'universe')
        self.header = self.wrapper((zip(header_fields, self.read_vdf_header())))
        if len(self.header) != len(header_fields):
            raise ValueError('Not all VDF headers are present, only found {num}: {header!r}'.format(
                num=len(header),
                header=self.header,
            ))

        # Currently these are the only possible values for
        # a valid appinfo.vdf
        if self.header['version'] not in VDF_VERSIONS:
            raise ValueError('Unknown VDF_VERSION: 0x{0:08x}'.format(self.header['version']))

        if self.header['universe'] != VDF_UNIVERSE:
            raise ValueError('Unknown VDF_UNIVERSE: 0x{0:08x}'.format(self.header['version']))

        # Store VDF_VERSION and VDF_UNIVERSE internally, as it's needed for proper encoding.
        self.parsed[b'__vdf_version'], self.parsed[b'__vdf_universe'] = self.header['version'], self.header['universe']

        # Parsing applications
        app_fields = ('size', 'state', 'last_update', 'access_token', 'checksum', 'change_number')
        while True:
            app_id = self._read_int32()

            # AppID = 0 marks the last application in the Appinfo
            if not app_id:
                break

            # All fields are required.
            app = self.wrapper((zip(app_fields, self.read_game_header())))
            if len(app) != len(app_fields):
                raise ValueError('Not all App headers are present, only found {num}: {header!r}'.format(
                    num=len(app),
                    header=app,
                ))

            # Store header and offset, then go to the next app
            self.app_headers[app_id] = app
            self.app_offsets[app_id] = self.offset
            self.offset += app['size'] - self.size_game_header + 4

    def decode(self, app_id):
        if app_id not in self.parsed:
            app = self.app_headers[app_id]
            self.offset = self.app_offsets[app_id]
            # The newest VDF format is a bit simpler to parse.
            if self.header['version'] == 0x07564427:
                app['sections'] = self.parse_subsections()
            else:
                app['sections'] = self.wrapper()
                while True:
                    section_id = self.read_byte()
                    if not section_id:
                        break

                    # Skip the 0x00 byte before section name.
                    self.offset += 1

                    section_name = self.read_string()
                    app['sections'][section_name] = self.parse_subsections(root_section=True)

                    # New Section ID's could be added in the future, or changes could be made to
                    # existing ones, so instead of maintaining a table of section names and their
                    # corresponding IDs, we are going to store the IDs with all the data.
                    app['sections'][section_name][b'__steamfiles_section_id'] = section_id

            self.parsed[app_id] = app

        return self.parsed[app_id]

    def parse_subsections(self, root_section=False):
        subsection = self.wrapper()

        while True:
            value_type = self.read_byte()
            if value_type == 0x08:
                if root_section:
                    # There's one additional 0x08 byte at the end of
                    # the root subsection.
                    self.offset += 1
                break

            key = self.read_string()
            value = self.value_parsers.get(value_type, self._unknown_value_type)()

            subsection[key] = value

        return subsection

    def make_custom_reader(self, fmt, single_value=False):
        custom_struct = struct.Struct(fmt)

        def return_many():
            result = custom_struct.unpack_from(self.data, self.offset)
            self.offset += custom_struct.size
            return result

        def return_one():
            result = custom_struct.unpack_from(self.data, self.offset)
            self.offset += custom_struct.size
            return result[0]

        if single_value:
            return return_one
        else:
            return return_many

    def read_int32(self):
        number = self._read_int32()
        return Integer(data=number, size=32)

    def read_int64(self):
        number = self._read_int64()
        return Integer(data=number, size=64)

    def read_byte(self):
        byte = self.data[self.offset]
        self.offset += 1
        return byte

    def read_string(self):
        # This method is pretty fast, provided we iterate over a memoryview.
        # It's also easier to read then the most performant ones, which is more important.
        for index, value in enumerate(self.data[self.offset:]):
            # NUL-byte – a string's end
            if value != 0:
                continue

            string = slice(self.offset, self.offset + index)
            self.offset += index + 1
            return self.data[string].tobytes()

    @staticmethod
    def _unknown_value_type():
        raise ValueError("Cannot parse the provided data type.")
