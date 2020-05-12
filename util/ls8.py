import random

def generate_easy_ls8(room_number):
    start_message = f"Mine your coin in room {room_number}"
    ls8_code = []
    # Load each character into R0 and print it
    for char in list(start_message):
        message_char = f"{ord(char):08b}"
        ls8_code.append("10000010") # LDI R1 message_char
        ls8_code.append("00000001")
        ls8_code.append(message_char)
        ls8_code.append("01001000") # PRA R1
        ls8_code.append("00000001")
    ls8_code.append("00000001") # HLT
    return "\n".join(ls8_code)

def generate_medium_ls8(room_number):
    start_message = f"Mine your coin in room "
    ls8_code = []
    room_digits = []
    # Append the first, second and third digits of the room number
    room_digits.append(f"{room_number // 100}")
    room_digits.append(f"{(room_number % 100) // 10}")
    room_digits.append(f"{room_number % 10}")
    # Load each character into R0 and print it
    for char in list(start_message):
        message_char = f"{ord(char):08b}"
        ls8_code.append("10000010") # LDI R1 message_char
        ls8_code.append("00000001")
        ls8_code.append(message_char)
        ls8_code.append("01001000") # PRA R1
        ls8_code.append("00000001")

    for digit in room_digits:
        # Load R1 with random value
        rand_x = random.randrange(0,256)
        ls8_code.append("10000010") # LDI R1, RAND_X
        ls8_code.append("00000001")
        ls8_code.append(f"{rand_x:08b}")

        # Load R2 with random value
        rand_y = random.randrange(0,256)
        ls8_code.append("10000010") # LDI R2, RAND_Y
        ls8_code.append("00000010")
        ls8_code.append(f"{rand_y:08b}")

        # R1 = rand_X AND rand_Y
        ls8_code.append("10101000") # AND R1 R2
        ls8_code.append("00000001")
        ls8_code.append("00000010")

        # XOR the random value with digit to get coerced value
        coerced_value = (rand_x & rand_y) ^ ord(digit)
        ls8_code.append("10000010") # LDI R2, COERCED_VALUE to "1"
        ls8_code.append("00000010")
        ls8_code.append(f"{coerced_value:08b}")

        # XOR with coerced to get room digit in R1
        ls8_code.append("10101011") # XOR R1 R2
        ls8_code.append("00000001")
        ls8_code.append("00000010")

        # Print room digit
        ls8_code.append("01001000") # PRA R1
        ls8_code.append("00000001")


    ls8_code.append("00000001") # HLT
    return "\n".join(ls8_code)


def generate_snitch_ls8(room_number):
    start_message = f"Find the snitch in room "
    ls8_code = []
    room_digits = []
    # Append the first, second and third digits of the room number
    room_digits.append(f"{room_number // 100}")
    room_digits.append(f"{(room_number % 100) // 10}")
    room_digits.append(f"{room_number % 10}")
    # Load each character into R0 and print it
    for char in list(start_message):
        message_char = f"{ord(char):08b}"
        ls8_code.append("10000010") # LDI R1 message_char
        ls8_code.append("00000001")
        ls8_code.append(message_char)
        ls8_code.append("01001000") # PRA R1
        ls8_code.append("00000001")

    for digit in room_digits:
        # Load R1 with random value
        rand_x = random.randrange(0,256)
        ls8_code.append("10000010") # LDI R1, RAND_X
        ls8_code.append("00000001")
        ls8_code.append(f"{rand_x:08b}")

        # Load R2 with random value
        rand_y = random.randrange(0,256)
        ls8_code.append("10000010") # LDI R2, RAND_Y
        ls8_code.append("00000010")
        ls8_code.append(f"{rand_y:08b}")

        # R1 = rand_X AND rand_Y
        ls8_code.append("10101000") # AND R1 R2
        ls8_code.append("00000001")
        ls8_code.append("00000010")

        # XOR the random value with digit to get coerced value
        coerced_value = (rand_x & rand_y) ^ ord(digit)
        ls8_code.append("10000010") # LDI R2, COERCED_VALUE to "1"
        ls8_code.append("00000010")
        ls8_code.append(f"{coerced_value:08b}")

        # XOR with coerced to get room digit in R1
        ls8_code.append("10101011") # XOR R1 R2
        ls8_code.append("00000001")
        ls8_code.append("00000010")

        # Print room digit
        ls8_code.append("01001000") # PRA R1
        ls8_code.append("00000001")


    ls8_code.append("00000001") # HLT
    return "\n".join(ls8_code)
