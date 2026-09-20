use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

fn interrupted(py: Python<'_>, output: &[u8], reads: usize, error: PyErr) -> PyErr {
    let value = error.value(py);
    let text: String = output.iter().map(|byte| char::from(*byte)).collect();
    let _ = value.setattr("_esolangs_native_output", text);
    let _ = value.setattr("_esolangs_native_reads", reads);
    error
}

fn output_text(output: &[u8]) -> String {
    output.iter().map(|byte| char::from(*byte)).collect()
}

#[pyfunction]
fn brainfuck(py: Python<'_>, code: &str, inputs: Vec<String>) -> PyResult<(String, usize, bool)> {
    let commands: Vec<char> = code.chars().collect();
    let mut partners = vec![usize::MAX; commands.len()];
    let mut stack = Vec::new();
    for (position, command) in commands.iter().enumerate() {
        match command {
            '[' => stack.push(position),
            ']' => {
                let Some(open) = stack.pop() else {
                    return Err(PyValueError::new_err(format!(
                        "unmatched ']' at position {position}"
                    )));
                };
                partners[open] = position;
                partners[position] = open;
            }
            _ => {}
        }
    }
    if let Some(position) = stack.pop() {
        return Err(PyValueError::new_err(format!(
            "unmatched '[' at position {position}"
        )));
    }

    let mut tape = vec![0_u8];
    let mut pointer = 0_usize;
    let mut instruction = 0_usize;
    let mut reads = 0_usize;
    let mut output = Vec::new();
    let mut ticks = 0_u16;
    while instruction < commands.len() {
        match commands[instruction] {
            '+' => tape[pointer] = tape[pointer].wrapping_add(1),
            '-' => tape[pointer] = tape[pointer].wrapping_sub(1),
            '>' => {
                pointer += 1;
                if pointer == tape.len() {
                    tape.push(0);
                }
            }
            '<' => pointer = pointer.saturating_sub(1),
            '[' if tape[pointer] == 0 => instruction = partners[instruction],
            ']' if tape[pointer] != 0 => instruction = partners[instruction],
            '.' => output.push(tape[pointer]),
            ',' => {
                let Some(line) = inputs.get(reads) else {
                    return Ok((output_text(&output), reads, true));
                };
                reads += 1;
                tape[pointer] = line.chars().next().map_or(0, |char| char as u32 as u8);
            }
            _ => {}
        }
        instruction += 1;
        ticks = ticks.wrapping_add(1);
        if ticks == 0
            && let Err(error) = py.check_signals()
        {
            return Err(interrupted(py, &output, reads, error));
        }
    }
    Ok((output_text(&output), reads, false))
}

#[pyfunction]
fn minifuck(py: Python<'_>, code: &str, inputs: Vec<String>) -> PyResult<(String, usize, bool)> {
    let commands: Vec<char> = code.chars().collect();
    let mut tape = vec![false; 8];
    let mut pointer = 0_usize;
    let mut instruction = 0_usize;
    let mut reads = 0_usize;
    let mut output = Vec::new();
    let mut ticks = 0_u16;
    while instruction < commands.len() {
        let command = commands[instruction];
        if command == '<' {
            pointer = pointer.saturating_sub(1);
            instruction += 1;
        } else if command == '.' || command == '[' {
            pointer += 1;
            if pointer + 1 >= tape.len() {
                tape.push(false);
            }
            tape[pointer] = !tape[pointer];
            if command == '.' {
                let byte = tape
                    .iter()
                    .take(8)
                    .enumerate()
                    .fold(0_u8, |value, (index, bit)| {
                        value | (u8::from(*bit) << (7 - index))
                    });
                if byte == 0 {
                    let Some(line) = inputs.get(reads) else {
                        return Ok((output_text(&output), reads, true));
                    };
                    reads += 1;
                    let byte = line.chars().next().map_or(0, |char| char as u32 as u8);
                    for (index, cell) in tape.iter_mut().take(8).enumerate() {
                        *cell = byte & (1 << (7 - index)) != 0;
                    }
                } else {
                    output.push(byte);
                }
                instruction += 1;
            } else if tape[pointer] {
                instruction += 1;
            } else {
                tape[pointer + 1] = !tape[pointer + 1];
                instruction += 2;
            }
        } else {
            instruction += 1;
        }
        ticks = ticks.wrapping_add(1);
        if ticks == 0
            && let Err(error) = py.check_signals()
        {
            return Err(interrupted(py, &output, reads, error));
        }
    }
    Ok((output_text(&output), reads, false))
}

fn rotated_at(commands: &[char], rotation: u8, instruction: usize) -> char {
    let opcode = match commands[instruction] {
        '+' => 0,
        '-' => 1,
        '>' => 2,
        '<' => 3,
        ',' => 4,
        '.' => 5,
        '[' => 6,
        ']' => 7,
        comment => return comment,
    };
    ['+', '-', '>', '<', ',', '.', '[', ']'][(opcode + usize::from(rotation)) % 8]
}

#[pyfunction]
fn rotfuck(py: Python<'_>, code: &str, inputs: Vec<String>) -> PyResult<(String, usize, u8)> {
    let commands: Vec<char> = code.chars().collect();
    let mut tape = vec![0_u8];
    let mut pointer = 0_usize;
    let mut instruction = 0_usize;
    let mut rotation = 0_u8;
    let mut reads = 0_usize;
    let mut output = Vec::new();
    let mut ticks = 0_u16;
    while instruction < commands.len() {
        let command = rotated_at(&commands, rotation, instruction);
        if command == '.' {
            output.push(tape[pointer]);
        } else if command == ',' {
            let Some(line) = inputs.get(reads) else {
                return Ok((output_text(&output), reads, 1));
            };
            reads += 1;
            tape[pointer] = line.chars().next().map_or(0, |char| char as u32 as u8);
        }

        match command {
            '>' => {
                pointer += 1;
                if pointer == tape.len() {
                    tape.push(0);
                }
            }
            '<' => pointer = pointer.saturating_sub(1),
            '+' => tape[pointer] = tape[pointer].wrapping_add(1),
            '-' => tape[pointer] = tape[pointer].wrapping_sub(1),
            '[' if tape[pointer] == 0 => {
                rotation = (rotation + 1) % 8;
                let mut depth = 1_usize;
                let mut cursor = instruction + 1;
                while cursor < commands.len() {
                    match rotated_at(&commands, rotation, cursor) {
                        '[' => depth += 1,
                        ']' => {
                            depth -= 1;
                            if depth == 0 {
                                break;
                            }
                        }
                        _ => {}
                    }
                    cursor += 1;
                }
                if depth != 0 {
                    return Ok((output_text(&output), reads, 2));
                }
                instruction = cursor + 1;
                continue;
            }
            ']' if tape[pointer] != 0 => {
                rotation = (rotation + 1) % 8;
                let mut depth = 1_usize;
                let mut cursor = instruction;
                while cursor > 0 {
                    cursor -= 1;
                    match rotated_at(&commands, rotation, cursor) {
                        ']' => depth += 1,
                        '[' => {
                            depth -= 1;
                            if depth == 0 {
                                break;
                            }
                        }
                        _ => {}
                    }
                }
                if depth != 0 {
                    return Ok((output_text(&output), reads, 3));
                }
                instruction = cursor + 1;
                continue;
            }
            _ => {}
        }
        if matches!(command, '+' | '-' | '>' | '<' | ',' | '.' | '[' | ']') {
            rotation = (rotation + 1) % 8;
        }
        instruction += 1;
        ticks = ticks.wrapping_add(1);
        if ticks == 0
            && let Err(error) = py.check_signals()
        {
            return Err(interrupted(py, &output, reads, error));
        }
    }
    Ok((output_text(&output), reads, 0))
}

#[pyfunction]
fn circlefuck(
    py: Python<'_>,
    mut cells: Vec<u8>,
    inputs: Vec<String>,
) -> PyResult<(String, usize, u8, usize)> {
    let mut instruction = 0_usize;
    let mut pointer = 0_usize;
    let mut reads = 0_usize;
    let mut output = Vec::new();
    let mut ticks = 0_u16;
    loop {
        let command = cells[instruction];
        if command == b'}' && cells.len() == 1 {
            return Ok((output_text(&output), reads, 4, instruction));
        }
        if command == b'.' {
            output.push(cells[pointer]);
        } else if command == b',' {
            let Some(line) = inputs.get(reads) else {
                return Ok((output_text(&output), reads, 1, instruction));
            };
            reads += 1;
            cells[pointer] = line.chars().next().map_or(0, |char| char as u32 as u8);
        }

        let mut size = cells.len();
        let mut edit = None;
        match command {
            b'>' => pointer = (pointer + 1) % size,
            b'<' => pointer = (pointer + size - 1) % size,
            b'+' => edit = Some((0_u8, pointer, cells[pointer].wrapping_add(1))),
            b'-' => edit = Some((0_u8, pointer, cells[pointer].wrapping_sub(1))),
            b',' => edit = Some((0_u8, pointer, cells[pointer])),
            b'[' | b']'
                if (command == b'[' && cells[pointer] == 0)
                    || (command == b']' && cells[pointer] != 0) =>
            {
                let forward = command == b'[';
                let start = instruction;
                let mut depth = if forward { 1_isize } else { -1_isize };
                loop {
                    instruction = if forward {
                        (instruction + 1) % size
                    } else {
                        (instruction + size - 1) % size
                    };
                    if instruction == start {
                        return Ok((
                            output_text(&output),
                            reads,
                            if forward { 2 } else { 3 },
                            start,
                        ));
                    }
                    match cells[instruction] {
                        b'[' => depth += 1,
                        b']' => depth -= 1,
                        _ => {}
                    }
                    if depth == 0 {
                        break;
                    }
                }
            }
            b'@' => return Ok((output_text(&output), reads, 0, instruction)),
            b'#' => instruction += 1,
            b'{' => {
                edit = Some((1_u8, pointer, 0));
                size += 1;
                instruction += 1;
            }
            b'}' => {
                edit = Some((2_u8, pointer, 0));
                size -= 1;
                pointer %= size;
            }
            _ => {}
        }
        instruction = (instruction + 1) % size;
        if let Some((kind, at, value)) = edit {
            match kind {
                0 => cells[at] = value,
                1 => cells.insert(at, value),
                _ => {
                    cells.remove(at);
                }
            }
        }
        ticks = ticks.wrapping_add(1);
        if ticks == 0
            && let Err(error) = py.check_signals()
        {
            return Err(interrupted(py, &output, reads, error));
        }
    }
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(brainfuck, module)?)?;
    module.add_function(wrap_pyfunction!(minifuck, module)?)?;
    module.add_function(wrap_pyfunction!(rotfuck, module)?)?;
    module.add_function(wrap_pyfunction!(circlefuck, module)?)?;
    Ok(())
}
