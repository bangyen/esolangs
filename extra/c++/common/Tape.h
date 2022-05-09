#pragma once
#ifndef TAPE_H
#define TAPE_H

#include "TapeCell.h"

class Tape {
public:
	TapeCell* curr;
	Tape();
	~Tape();
	int value();
	void add(int value);
	void set(int value);
	void next();
	void prev();
	void start();
	void end();
};

#endif
