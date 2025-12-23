from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 100), 'white')
draw = ImageDraw.Draw(img)
draw.text((10, 30), 'Hello World', fill='black')
img.save('test.png')
print('Created test.png')
