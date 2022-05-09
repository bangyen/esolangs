#include "TapeCell.h"

TapeCell::TapeCell() {
	value = 0;
	prev = nullptr;
	next = nullptr;
}

void TapeCell::set(int val) {
	value = val;
}