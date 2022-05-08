#pragma once
#ifndef TAPECELL_H
#define TAPECELL_H

class TapeCell {
public:
	int value;
	TapeCell* prev;
	TapeCell* next;

	TapeCell();
	void set(int val);
};

#endif