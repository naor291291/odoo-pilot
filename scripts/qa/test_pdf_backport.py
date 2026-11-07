"""Bounded regression: never allow the original EOF loop to consume a worker."""
from io import BytesIO
import unittest
from PyPDF2.generic import ContentStream, DecodedStreamObject


class LimitedReads(BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.read_count = 0

    def read(self, size=-1):
        self.read_count += 1
        if self.read_count > 100:
            raise AssertionError('PDF EOF comment loop exceeded bounded read budget')
        return super().read(size)


class PdfBackportTests(unittest.TestCase):
    def test_unterminated_comment_stops_at_eof(self):
        parser = ContentStream.__new__(ContentStream)
        parser.operations = []
        parser.forced_encoding = None
        stream = LimitedReads(b'%synthetic EOF comment')
        parser._ContentStream__parse_content_stream(stream)
        self.assertEqual(parser.operations, [])
        self.assertLess(stream.read_count, 100)

    def test_comment_does_not_discard_following_operators(self):
        stream = DecodedStreamObject()
        stream.set_data(b'%comment\nq\nQ\n%last comment\n')
        self.assertEqual(ContentStream(stream, None).operations, [([], b'q'), ([], b'Q')])


if __name__ == '__main__':
    unittest.main()
