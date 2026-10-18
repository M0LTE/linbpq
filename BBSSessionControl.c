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
//	BBS session control for partner forwarding on shared channels
//
//	- INTERLOCK <port> and INTERLOCK GROUP <n> (ports with INTERLOCK=n in
//	  bpq32.cfg) in connect scripts, applied to incoming connects as well
//	  as dial-outs
//	- Per-partner MaxSessionTime and SessionLockout
//	- Logging of partner session length
//
//	Called from hooks in BBSUtilities.c

#include "bpqmail.h"

extern ConnectionInfo Connections[];
extern int NumberofStreams;
extern struct UserInfo * BBSChain;

int GetPortInterlockGroup(int Port)
{
	// INTERLOCK=n from the port's bpq32.cfg PORT block, or 0

	struct PORTCONTROL * PORT;

	if (Port == 0)
		return 0;

	PORT = GetPortTableEntryFromPortNum(Port);

	if (PORT == NULL)
		return 0;

	return PORT->PORTINTERLOCK;
}

int CountInterlockConnections(int Port, int Group, BOOL PartnersOnly)
{
	// Count BBS sessions on Port, or if Group is set on any port with
	// INTERLOCK=Group in bpq32.cfg. PartnersOnly counts only sessions
	// with partner BBSes (mail runs)

	int n, Count = 0;
	CIRCUIT * conn;
	int port, sesstype, paclen, maxframe, l4window;
	char callsign[11];

	for (n = 0; n < NumberofStreams; n++)
	{
		conn = &Connections[n];

		if (conn->Active)
		{
			if (PartnersOnly && (conn->UserPointer == NULL || (conn->UserPointer->flags & F_BBS) == 0))
				continue;

			GetConnectionInfo(conn->BPQStream, callsign, &port, &sesstype, &paclen, &maxframe, &l4window);

			if (port == 0)
				continue;

			if (Group ? GetPortInterlockGroup(port) == Group : port == Port)
				Count++;
		}
	}

	return Count;
}

BOOL IsNamedInInterlock(int Num, BOOL Group)
{
	// See if a port (INTERLOCK n) or interlock group (INTERLOCK GROUP n) is named
	// in any BBS connect script. Used to apply the interlock to incoming BBS
	// connects as well as outgoing

	struct UserInfo * user;
	char ** Scripts;

	if (Num == 0)
		return FALSE;

	for (user = BBSChain; user; user = user->BBSNext)
	{
		if (user->ForwardingInfo == NULL)
			continue;

		Scripts = user->ForwardingInfo->ConnectScript;

		while (Scripts && Scripts[0])
		{
			if (_memicmp(Scripts[0], "INTERLOCK GROUP ", 16) == 0)
			{
				if (Group && atoi(&Scripts[0][16]) == Num)
					return TRUE;
			}
			else if (_memicmp(Scripts[0], "INTERLOCK ", 10) == 0)
			{
				if (!Group && atoi(&Scripts[0][10]) == Num)
					return TRUE;
			}

			Scripts++;
		}
	}
	return FALSE;
}

BOOL ScriptInterlockGroup(CIRCUIT * conn, char * Cmd)
{
	// Connect script INTERLOCK GROUP n. Limits connects to 1 across all ports
	// with INTERLOCK=n in bpq32.cfg. Returns FALSE, having disconnected, if
	// the group is busy

	int Group = atoi(&Cmd[16]);

	Logprintf(LOG_BBS, conn, '?', "Script %s", Cmd);

	if (Group && CountInterlockConnections(0, Group, FALSE))
	{
		Logprintf(LOG_BBS, conn, '?', "Interlock Group %d is busy - quitting", Group);
		conn->BBSFlags &= ~RunningConnectScript;	// so it doesn't get reentered
		Disconnect(conn->BPQStream);
		return FALSE;
	}

	return TRUE;
}

BOOL SessionLockedOut(struct UserInfo * user)
{
	// Don't dial out to a partner locked out after hitting MaxSessionTime

	struct BBSForwardingInfo * ForwardingInfo = user->ForwardingInfo;

	if (ForwardingInfo->LockoutUntil > time(NULL))
	{
		Logprintf(LOG_BBS, NULL, '|', "Not connecting to BBS %s - locked out for %d more secs after MaxSessionTime",
			user->Call, (int)(ForwardingInfo->LockoutUntil - time(NULL)));
		return TRUE;
	}

	return FALSE;
}

BOOL RefuseIncomingSession(CIRCUIT * conn, struct UserInfo * user, int port)
{
	// See if an incoming connect should be refused. Returns TRUE, having logged
	// why, if so. Caller disconnects

	BOOL Partner = (user->flags & F_BBS) != 0;
	int Group = GetPortInterlockGroup(port);
	int Others = Partner ? 1 : 0;

	if (Partner && user->ForwardingInfo && user->ForwardingInfo->LockoutUntil > time(NULL))
	{
		Logprintf(LOG_BBS, conn, '|', "Incoming Connect from %s Rejected - locked out for %d more secs after MaxSessionTime",
			user->Call, (int)(user->ForwardingInfo->LockoutUntil - time(NULL)));
		return TRUE;
	}

	// Interlocked ports and groups: a partner BBS is refused while any other
	// BBS session is on them, anyone else while a partner session (a mail
	// run) is. Counts include this session, which is only counted for partners

	if (IsNamedInInterlock(port, FALSE) && CountInterlockConnections(port, 0, !Partner) > Others)
	{
		Logprintf(LOG_BBS, conn, '|', "Incoming Connect from %s Rejected - Interlocked Port %d is busy", user->Call, port);
		if (!Partner)
			nodeprintf(conn, "Sorry, mail forwarding in progress on this channel. Please try later\r");
		return TRUE;
	}

	if (Group && IsNamedInInterlock(Group, TRUE) && CountInterlockConnections(0, Group, !Partner) > Others)
	{
		Logprintf(LOG_BBS, conn, '|', "Incoming Connect from %s Rejected - Interlock Group %d is busy", user->Call, Group);
		if (!Partner)
			nodeprintf(conn, "Sorry, mail forwarding in progress on this channel. Please try later\r");
		return TRUE;
	}

	return FALSE;
}

void CheckMaxSessionTime(CIRCUIT * conn)
{
	// Called every 10 seconds for each active session. Disconnects partner
	// sessions over MaxSessionTime and starts the partner's lockout

	struct BBSForwardingInfo * FWDInfo;
	time_t NOW = time(NULL);

	if (conn->SessionStartTime == 0 || conn->MaxSessionTimeHit || conn->UserPointer == NULL ||
		(conn->UserPointer->flags & F_BBS) == 0 || conn->UserPointer->ForwardingInfo == NULL)
		return;

	FWDInfo = conn->UserPointer->ForwardingInfo;

	if (FWDInfo->MaxSessionTime && (NOW - conn->SessionStartTime) >= FWDInfo->MaxSessionTime * 60)
	{
		Logprintf(LOG_BBS, conn, '|', "Session exceeded MaxSessionTime of %d mins - disconnecting, locked out for %d mins",
			FWDInfo->MaxSessionTime, FWDInfo->SessionLockout);

		FWDInfo->LockoutUntil = NOW + FWDInfo->SessionLockout * 60;
		conn->MaxSessionTimeHit = TRUE;				// Only once
		conn->BBSFlags &= ~RunningConnectScript;	// Don't try ELSE alternatives
		Disconnect(conn->BPQStream);
	}
}

void LogSessionLength(CIRCUIT * conn)
{
	// Log how long a partner session lasted. Only sessions that got as far as
	// the SID exchange. Outgoing sessions are timed from the start of the
	// connect script

	int Secs;

	if (conn->SessionStartTime == 0 || (conn->BBSFlags & BBS) == 0 || conn->UserPointer == NULL ||
		(conn->UserPointer->flags & F_BBS) == 0)
		return;

	Secs = (int)(time(NULL) - conn->SessionStartTime);

	Logprintf(LOG_BBS, conn, '|', "Partner session lasted %d mins %d secs%s", Secs / 60, Secs % 60,
		conn->MaxSessionTimeHit ? " (cut off by MaxSessionTime)" : "");
}
