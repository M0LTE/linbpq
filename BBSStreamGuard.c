/*
Copyright 2001-2018 John Wiseman G8BPQ

This file is part of LinBPQ/BPQ32.

LinBPQ/BPQ32 is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

LinBPQ/BPQ32 is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with LinBPQ/BPQ32.  If not, see http://www.gnu.org/licenses
*/

// Mail Server for BPQ32 Packet Switch
//
//	Don't read a BBS stream's data before its connect has been processed
//
//	PollStreams reads each stream's data before it checks the stream's
//	state. If a connect and the caller's first line arrive in the same
//	poll (for example a USER line that starts the BBS, followed at once
//	by the next line from the client), the line was handed to ProcessLine
//	with the previous session's ConnectionInfo: a NULL user on a stream
//	never used before (SIGSEGV), or the last user's record otherwise.
//	M0LTE/linbpq#86.
//
//	Called from a hook at the top of DoReceivedData in BBSUtilities.c

#include "bpqmail.h"

extern struct SEM ConSemaphore;

BOOL BBSStreamReadyForData(CIRCUIT * conn)
{
	// TRUE if DoReceivedData can go on and read this stream's data

	int state, change;
	int len, count;
	char Discard[1024];

	if (conn->Active && conn->UserPointer)
		return TRUE;

	// Handle a pending connect (or disconnect) now, as PollStreams would
	// have done after reading the data

	SessionState(conn->BPQStream, &state, &change);

	if (change)
	{
		GetSemaphore(&ConSemaphore, 0);

		if (state == 1)
			Connected(conn->BPQStream);
		else
			Disconnected(conn->BPQStream);

		FreeSemaphore(&ConSemaphore);

		if (conn->Active && conn->UserPointer)
			return TRUE;
	}

	// No session to give the data to (refused, or already gone). Drop it

	do
	{
		GetMsg(conn->BPQStream, Discard, &len, &count);
	} while (len);

	return FALSE;
}
