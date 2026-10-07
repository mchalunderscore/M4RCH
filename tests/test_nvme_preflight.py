import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import uuid
import zlib

spec = importlib.util.spec_from_file_location('nvme_preflight', Path(__file__).resolve().parents[1]/'scripts/nvme-preflight.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class GPTReadTests(unittest.TestCase):
    def image(self):
        image = bytearray(64*4096)
        entries = bytearray(4*128)
        for i,(start,end) in enumerate(((6,10),(11,61))):
            entry = bytearray(128)
            entry[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le
            entry[16:32]=uuid.UUID(int=i+1).bytes_le
            struct.pack_into('<QQQ',entry,32,start,end,0)
            entries[i*128:(i+1)*128]=entry
        for current,other,table in ((1,63,2),(63,1,62)):
            block=bytearray(4096);block[:8]=b'EFI PART'
            struct.pack_into('<IIII',block,8,0x10000,92,0,0)
            struct.pack_into('<QQQQ',block,24,current,other,6,61)
            block[56:72]=uuid.UUID(int=42).bytes_le
            struct.pack_into('<QIII',block,72,table,4,128,zlib.crc32(entries))
            struct.pack_into('<I',block,16,zlib.crc32(block[:92]))
            image[current*4096:(current+1)*4096]=block
            image[table*4096:table*4096+len(entries)]=entries
        return image

    def test_read_preserves_image_and_saves_both_regions(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'disk';data=self.image();path.write_bytes(data)
            header,parts,head,tail,offset=m.read_gpt(path,4096,len(data))
            self.assertEqual(len(parts),2)
            self.assertEqual(parts[0]['offset'],6*4096)
            self.assertEqual(head,data[:len(head)])
            self.assertEqual(tail,data[offset:])
            self.assertEqual(path.read_bytes(),data)

    def test_reject_primary_header_or_entry_corruption(self):
        for offset in (4096+24,8192+40,62*4096+40):
            with self.subTest(offset=offset), tempfile.TemporaryDirectory() as d:
                path=Path(d)/'disk';data=self.image();data[offset]^=1;path.write_bytes(data)
                with self.assertRaises(ValueError):m.read_gpt(path,4096,len(data))

if __name__=='__main__':unittest.main()
