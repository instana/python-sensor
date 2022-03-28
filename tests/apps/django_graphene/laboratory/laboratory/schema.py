import graphene
from graphene_django import DjangoObjectType

from laboratory.materials.models import Category, Material

class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = ("id", "name", "ingredients")

class IngredientType(DjangoObjectType):
    class Meta:
        model = Material
        fields = ("id", "name", "notes", "category")

class Query(graphene.ObjectType):
    all_materials = graphene.List(IngredientType)
    category_by_name = graphene.Field(CategoryType, name=graphene.String(required=True))

    def resolve_all_materials(root, info):
        # We can easily optimize query count in the resolve method
        return Material.objects.select_related("category").all()

    def resolve_category_by_name(root, info, name):
        try:
            return Category.objects.get(name=name)
        except Category.DoesNotExist:
            return None

schema = graphene.Schema(query=Query)

