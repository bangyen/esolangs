use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

fn interrupted(py: Python<'_>, output: &[u8], reads: usize, error: PyErr) -> PyErr {
    let value = error.value(py);
    let text: String = output.iter().map(|byte| char::from(*byte)).collect();
    let _ = value.setattr("_esolangs_native_output", text);
    let _ = value.setattr("_esolangs_native_reads", reads);
    error
}

#[pyfunction]
fn brainfuck(py: Python<'_>, code: &str, input: Vec<String>) -> PyResult<(String, usize, bool)> {
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
                let Some(line) = input.get(reads) else {
                    let text: String = output.iter().map(|byte| char::from(*byte)).collect();
                    return Ok((text, reads, true));
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
    let text: String = output.iter().map(|byte| char::from(*byte)).collect();
    Ok((text, reads, false))
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(brainfuck, module)?)?;
    Ok(())
}
