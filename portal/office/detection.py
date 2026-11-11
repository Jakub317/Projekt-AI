import random

def simulate_detection(photo):
    n = random.randint(1, 5)
    return [
        {"x": random.randint(0, 800), "y": random.randint(0, 600),
         "w": random.randint(50, 150), "h": random.randint(50, 150),
         "confidence": round(random.uniform(0.6, 0.98), 2)}
        for _ in range(n)
    ]

def detect_frames(photo):
    # TERAZ: symulacja. PÓŹNIEJ: wywołanie API studentów.
    return simulate_detection(photo)
