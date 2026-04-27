// CmdLineAuth.cpp : Defines the entry point for the console application.
//

#define WIN32_LEAN_AND_MEAN		// Exclude rarely-used stuff from Windows headers
#define _CRT_SECURE_NO_DEPRECATE 

#define _USE_32BIT_TIME_T

#include <stdio.h>
#include <time.h>
#include <string.h>

#include "md5.c"


int GetOneTimePasswordCode(const char * KeyPhrase, time_t Now)
{
	// Create a time dependent One Time Password from the KeyPhrase
	unsigned char Hash[16];
	char Password[20];
	char Key[1000];
	int i, chr;
	long long Val;

	Now = Now/30;							// Only Change every 30 secs

	sprintf(Key, "%s%x", KeyPhrase, (unsigned int)Now);

	md5(Key, Hash);

	for (i=0; i<16; i++)
	{
		chr = (Hash[i] & 31);
		if (chr > 9) chr += 7;
		
		Password[i] = chr + 48; 
	}

	Password[16] = 0;

	memcpy(&Val, Password, 8);
	return Val % 1000000;
}

VOID CreateOneTimePassword(char * KeyPhrase)
{
	int PassCode = GetOneTimePasswordCode(KeyPhrase, time(NULL));

	printf("Passcode is %06d\n", PassCode);

	return;
}

int main(int argc, char * argv[])
{
	if (argc < 2)
	{
		printf ("Need to supply KeyPhrase\n");
		return 0;
	}
	CreateOneTimePassword(argv[1]);
	return 0;
}

