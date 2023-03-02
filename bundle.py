from archive import *
from conf import *
from connection import *
from message import *
from timeout import *

import getopt
import os
import sys

sign = False
verbose = False
create = False
extract = False

filelist = []
archive = None

truesig = None
claimedsig = None

def usage(err):
	print(err)
	print("usage:")
	print(f"	{sys.argv[0]} [-sv] -c -f archivename files...")
	print(f"	{sys.argv[0]} [-sv] -x -f archivename")
	sys.exit(2)

try: opts, args = getopt.getopt(sys.argv[1:], "cxsvf:")
except getopt.GetoptError as err: usage(err)

for o, a in opts:
	if o == '-c': create = True
	elif o == '-x': extract = True
	elif o == '-s': sign = True
	elif o == '-v': verbose = True
	elif o == '-f': archive = a

if create and extract:
	usage("cannot extract _and_ create an archive simultaneously")

if not create and not extract:
	usage("must specify either -c or -x")

if archive is None:
	usage("no archive filename specified")

filelist = args
if not filelist and create:
	usage("no input files specified")
elif filelist and extract:
	usage("tried to specify input files to extract operation")

conn = Connection([server_ca, client_ca], client_cert, client_key)
conn.connect(server_hostname, server_port)

if extract:
	object = None
	with open(archive, 'rb') as f:
		archivebytes = f.read()
		object = Archive.from_bytes(archivebytes)

	for fname in object.all_filenames():
		fileobj = object.get_file_by_name(fname)
		filecontent = fileobj.uncompressed_content()

		if verbose: print(fname)

		directory = os.path.dirname(fname)
		if directory != '' and not os.path.exists(directory):
			os.makedirs(directory)

		with open(fname, 'wb') as f:
			f.write(filecontent)

	if sign:
		create = True
		filelist = object.all_filenames()
		claimedsig = object.signature()

if create:
	for fname in filelist:
		if verbose and not extract: print(fname)

		if os.path.isdir(fname):
			filelist.extend([f"{fname}/{cf}" for cf in os.listdir(fname)])
			continue

		fnamebytes = bytes(fname, 'ascii')

		with open(fname, 'rb') as f:
			content = f.read()
			message = Message(MessageOp.WRITE, label=fnamebytes, file=content)
			conn.write_bytes(message.to_bytes())

		to = Timeout(1)
		response = Message.from_conn(conn)
		to.cancel()

		if response.opcode() != MessageOp.ACK:
			raise ValueError(f"received bad reply from server ({response.opcode()})")

	if sign:
		message = Message(MessageOp.SIGN)
		conn.write_bytes(message.to_bytes())

		to = Timeout(1)
		response = Message.from_conn(conn)
		to.cancel()

		if response.opcode() != MessageOp.ACK:
			raise ValueError(f"received bad reply from server ({response.opcode()})")

	
	
	message = Message(MessageOp.GETBUNDLE)
	conn.write_bytes(message.to_bytes())

	to = Timeout(1)
	response = Message.from_conn(conn)
	to.cancel()

	if response.opcode() != MessageOp.BUNDLE:
		raise ValueError(f"received bad reply from server ({response.opcode()})")

	if not extract:
		with open(archive, 'wb') as f:
			f.write(response.file())
	else:
		object = Archive.from_bytes(response.file())
		if object.signature() != claimedsig:
			raise ValueError("signature is incorrect on extracted archive!")
		elif verbose: print("signature verified")

		

conn.close()
