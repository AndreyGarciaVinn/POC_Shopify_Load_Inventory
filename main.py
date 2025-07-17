from services.Shopify_Inventory import ShopifyInventoryManager
import json

def main():
    """Ejemplo de uso"""
    try:
        manager = ShopifyInventoryManager()
        
        # 1. Obtener ubicaciones
        print("Ubicaciones disponibles:")
        locations = manager.get_locations()
        for location in locations:
            print(f"  - {location['name']} (ID: {location['id']}) - {location['city']}")
    
        use_Location = locations[1]['gid']
        location_Invetory_Summary = manager.get_inventory_summary_by_location(use_Location)
        location_Inventory_Detailed = manager.get_inventory_with_product_info(use_Location)

        print(f"Inventario de {location_Invetory_Summary}:")
        print(json.dumps(location_Inventory_Detailed, indent=4)) # los acentos se ven raros (no lo cambiare a utf-8)
        
    except Exception as e:
        print(f"i really hts: ", e)


if __name__ == "__main__":
    main()