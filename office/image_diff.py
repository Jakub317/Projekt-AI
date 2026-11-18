from PIL import Image, ImageChops
import io

def compare_images(image1_path, image2_path, threshold=30):
    """
    Porównuje dwa zdjęcia i zwraca listę obszarów, które się różnią.
    threshold: jak bardzo piksele muszą się różnić (0-255)
    """
    try:
        img1 = Image.open(image1_path).convert('RGB')
        img2 = Image.open(image2_path).convert('RGB')
        
        # Dopasuj rozmiary (jeśli różne)
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
        
        # Oblicz różnicę między zdjęciami
        diff = ImageChops.difference(img1, img2)
        
        # Znajdź obszary z różnicami
        diff_array = list(diff.getdata())
        width, height = img1.size
        
        changed_regions = []
        block_size = 50  # Analizuj bloki 50x50 pikseli
        
        for y in range(0, height, block_size):
            for x in range(0, width, block_size):
                # Pobierz blok pikseli
                block_pixels = []
                for dy in range(block_size):
                    for dx in range(block_size):
                        if y + dy < height and x + dx < width:
                            idx = (y + dy) * width + (x + dx)
                            if idx < len(diff_array):
                                block_pixels.append(diff_array[idx])
                
                if block_pixels:
                    # Oblicz średnią różnicę w bloku
                    avg_diff = sum(sum(p) for p in block_pixels) / (len(block_pixels) * 3)
                    
                    if avg_diff > threshold:
                        # Ten blok się różni - dodaj go
                        changed_regions.append({
                            'x_pct': (x / width) * 100,
                            'y_pct': (y / height) * 100,
                            'w_pct': (block_size / width) * 100,
                            'h_pct': (block_size / height) * 100,
                            'confidence': min(100, avg_diff)
                        })
        
        return changed_regions
    except Exception as e:
        print(f"Błąd porównywania: {e}")
        return []
