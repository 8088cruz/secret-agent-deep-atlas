"""Caesar cipher decryptor gadget for Secret Agents."""

from __future__ import annotations


def decrypt_message(ciphertext: str, shift: int) -> str:
    """Decrypt a Caesar-shifted message.

    `shift` is the number of characters the ciphertext was shifted forward.
    Decryption shifts letters backward by that amount. Non-letters are kept.
    """
    normalized_shift = int(shift) % 26
    decrypted = []

    for char in str(ciphertext):
        if "A" <= char <= "Z":
            base = ord("A")
            decrypted.append(chr(((ord(char) - base - normalized_shift) % 26) + base))
        elif "a" <= char <= "z":
            base = ord("a")
            decrypted.append(chr(((ord(char) - base - normalized_shift) % 26) + base))
        else:
            decrypted.append(char)

    return f"Unencrypted message: {''.join(decrypted)}"
