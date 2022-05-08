#include "Tape.h"

Tape::Tape() {
	curr = new TapeCell;
}

Tape::~Tape() {
	start();
	while (curr->next != nullptr) {
		next();
		delete curr->prev;
	}

	delete curr;
}

int Tape::value() {
	return curr->value;
}

void Tape::add(int val) {
	curr->set(value() + val);
}

void Tape::set(int val) {
	curr->set(val);
}

void Tape::next() {
	TapeCell* next = curr->next;

	if (next != nullptr) {
		curr = next;
	} else {
		curr->next = new TapeCell;
		curr->next->prev = curr;
		curr = curr->next;
	}
}

void Tape::prev() {
	TapeCell* prev = curr->prev;

	if (prev != nullptr) {
		curr = prev;
	} else {
		curr->prev = new TapeCell;
		curr->prev->next = curr;
		curr = curr->prev;
	}
}

void Tape::start() {
	while (curr->prev != nullptr)
		curr = curr->prev;
}

void Tape::end() {
	while (curr->next != nullptr)
		curr = curr->next;
}