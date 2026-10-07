# -*- coding: utf-8 -*-
"""
Script untuk menghasilkan data/Katalog_Komputer_RAG.pdf riil
TANPA baris artifisial 'Penggunaan yang disarankan:'.
"""
import pymupdf

OUTPUT_PDF = "data/Katalog_Komputer_RAG.pdf"

PAGES_DATA = [
    # PAGE 1: COVER / INTRO
    """Katalog Komputer, Laptop & Printer - Data Knowledge Base
Toko Komputer Bobby Computer

Katalog produk resmi Bobby Computer mencakup 10 Laptop, 5 Desktop PC, dan 5 Printer dari merek-merek ternama seperti Acer, Lenovo, ASUS, HP, Canon, Epson, dan Brother.

Petunjuk Penggunaan:
Dokumen ini merupakan sumber pengetahuan produk untuk sistem Customer Service Bobby Computer. Seluruh data spesifikasi teknis, harga, fitur cetak, dan kelengkapan perangkat tercantum secara faktual. Kesesuaian beban kerja (workload) dianalisis berdasarkan spesifikasi teknis perangkat keras.""",

    # PAGE 2: LAPTOPS 1 - 4
    """Detail Produk dan Product Knowledge

KB-L01 - Acer Aspire Lite 14
Jenis: Laptop
Harga: Rp5.199.000
Prosesor: Intel Processor N100
RAM: 8 GB DDR5
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics
Display: 14 inci WUXGA IPS
Sistem operasi: Windows 11 Home

KB-L02 - Lenovo IdeaPad Slim 3 14
Jenis: Laptop
Harga: Rp7.299.000
Prosesor: Intel Core i3-1215U
RAM: 8 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics
Display: 14 inci FHD
Sistem operasi: Windows 11 Home

KB-L03 - ASUS Vivobook 14 A1405
Jenis: Laptop
Harga: Rp8.799.000
Prosesor: Intel Core i5-1235U
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel Iris Xe
Display: 14 inci WUXGA IPS
Sistem operasi: Windows 11 Home

KB-L04 - HP 14s-fq1036AU
Jenis: Laptop
Harga: Rp9.499.000
Prosesor: AMD Ryzen 5 7530U
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: AMD Radeon Graphics
Display: 14 inci FHD IPS
Sistem operasi: Windows 11 Home""",

    # PAGE 3: LAPTOPS 5 - 8
    """KB-L05 - Lenovo IdeaPad Slim 5 14
Jenis: Laptop
Harga: Rp11.499.000
Prosesor: AMD Ryzen 7 7730U
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: AMD Radeon Graphics
Display: 14 inci WUXGA OLED
Sistem operasi: Windows 11 Home

KB-L06 - Acer Nitro V 15
Jenis: Laptop
Harga: Rp12.999.000
Prosesor: Intel Core i5-13420H
RAM: 16 GB DDR5
Storage: 512 GB NVMe SSD
GPU: NVIDIA GeForce RTX 2050 4 GB
Display: 15,6 inci FHD 144 Hz
Sistem operasi: Windows 11 Home

KB-L07 - ASUS Vivobook Pro 15 OLED
Jenis: Laptop
Harga: Rp13.499.000
Prosesor: AMD Ryzen 7 7735HS
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 3050 6 GB
Display: 15,6 inci 2.8K OLED
Sistem operasi: Windows 11 Home

KB-L08 - Lenovo LOQ 15
Jenis: Laptop
Harga: Rp14.799.000
Prosesor: Intel Core i5-12450HX
RAM: 16 GB DDR5
Storage: 512 GB NVMe SSD
GPU: NVIDIA GeForce RTX 4050 6 GB
Display: 15,6 inci FHD 144 Hz 100% sRGB
Sistem operasi: Windows 11 Home""",

    # PAGE 4: LAPTOPS 9-10 & DESKTOPS 1-2
    """KB-L09 - ASUS TUF Gaming A15
Jenis: Laptop
Harga: Rp16.999.000
Prosesor: AMD Ryzen 7 7735HS
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4060 8 GB
Display: 15,6 inci FHD 144 Hz 100% sRGB
Sistem operasi: Windows 11 Home

KB-L10 - Lenovo Legion Pro 5 16
Jenis: Laptop
Harga: Rp23.999.000
Prosesor: Intel Core i7-14650HX
RAM: 32 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4070 8 GB
Display: 16 inci WQXGA 240 Hz
Sistem operasi: Windows 11 Home

KB-D01 - Lenovo IdeaCentre Mini 01
Jenis: Desktop
Harga: Rp6.999.000
Prosesor: Intel Core i3-13100T
RAM: 8 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics 730
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-D02 - ASUS ExpertCenter D500 Tower
Jenis: Desktop
Harga: Rp9.899.000
Prosesor: Intel Core i5-12400
RAM: 16 GB DDR4
Storage: 512 GB NVMe SSD
GPU: Intel UHD Graphics 730
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home""",

    # PAGE 5: DESKTOPS 3-5 & PRINTER 1
    """KB-D03 - HP Pavilion Desktop TP01
Jenis: Desktop
Harga: Rp13.499.000
Prosesor: Intel Core i5-13400
RAM: 16 GB DDR4
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce GTX 1660 Super 6 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-D04 - Lenovo LOQ Tower 17
Jenis: Desktop
Harga: Rp17.999.000
Prosesor: Intel Core i5-13400F
RAM: 16 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4060 8 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-D05 - ASUS ROG Strix G16CHR
Jenis: Desktop
Harga: Rp27.499.000
Prosesor: Intel Core i7-14700F
RAM: 32 GB DDR5
Storage: 1 TB NVMe SSD
GPU: NVIDIA GeForce RTX 4070 12 GB
Display: Tidak termasuk monitor
Sistem operasi: Windows 11 Home

KB-P01 - Canon PIXMA TS207
Jenis: Printer
Harga: Rp699.000
Fungsi: Print Only
Teknologi: Inkjet Cartridge
Kecepatan: 7,7 ipm hitam / 4,0 ipm warna
Resolusi: 4800 x 1200 dpi
Konektivitas: USB 2.0""",

    # PAGE 6: PRINTERS 2-5
    """KB-P02 - Epson EcoTank L121
Jenis: Printer
Harga: Rp1.699.000
Fungsi: Print Only
Teknologi: Ink Tank
Kecepatan: 9,0 ipm hitam / 4,8 ipm warna
Resolusi: 720 x 720 dpi
Konektivitas: USB 2.0

KB-P03 - Epson EcoTank L3210
Jenis: Printer
Harga: Rp2.299.000
Fungsi: Print, Scan, Copy
Teknologi: Ink Tank
Kecepatan: 10,0 ipm hitam / 5,0 ipm warna
Resolusi: 5760 x 1440 dpi
Konektivitas: USB 2.0

KB-P04 - Canon PIXMA G3020
Jenis: Printer
Harga: Rp2.599.000
Fungsi: Print, Scan, Copy
Teknologi: Ink Tank
Kecepatan: 9,1 ipm hitam / 5,0 ipm warna
Resolusi: 4800 x 1200 dpi
Konektivitas: Wi-Fi, USB 2.0, Mobile Printing

KB-P05 - Brother DCP-T520W
Jenis: Printer
Harga: Rp2.999.000
Fungsi: Print, Scan, Copy
Teknologi: Ink Tank
Kecepatan: 17,0 ipm hitam / 9,5 ipm warna
Resolusi: 1200 x 6000 dpi
Konektivitas: Wi-Fi, USB 2.0, Mobile Printing""",

    # PAGE 7: KEBIJAKAN KNOWLEDGE BASE
    """Kebijakan Knowledge Base

Topik: Aturan
Harga: Harga yang tercantum adalah harga resmi pada katalog ini.
Ketersediaan: Dokumen ini tidak menyediakan data kuantitas stok realtime.
Kesesuaian: Chatbot menganalisis kesesuaian berdasarkan spesifikasi perangkat keras dan kebutuhan komputasi pelanggan.
Kategori: Toko melayani penjualan Laptop, Desktop, dan Printer."""
]

def main():
    doc = pymupdf.open()
    for text in PAGES_DATA:
        page = doc.new_page(width=595, height=842) # A4
        # Margin 50, 50, 545, 792
        rect = pymupdf.Rect(50, 50, 545, 792)
        page.insert_textbox(rect, text.strip(), fontsize=11, fontname="helv")
    
    doc.save(OUTPUT_PDF)
    print(f"Berhasil membuat PDF baru: {OUTPUT_PDF} ({len(doc)} halaman)")

if __name__ == "__main__":
    main()
