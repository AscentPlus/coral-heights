from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError

from staff_panel.permissions import website_access_required
from .models import (
    HotelInfo, RestaurantInfo, MenuCategory, MenuItem,
    NearbyPlace, ChatFAQ, UnansweredQuestion
)
from .forms import (
    HotelInfoForm, RestaurantInfoForm, MenuCategoryForm, MenuItemForm,
    NearbyPlaceForm, ChatFAQForm
)


@website_access_required
def website_hotel_details(request):
    """
    Staff page to manage singleton HotelInfo: check-in/out timings,
    parking, Wi-Fi, payments, languages, pet policy, rate note.
    """
    hotel_info = HotelInfo.load()
    if request.method == 'POST':
        form = HotelInfoForm(request.POST, instance=hotel_info)
        if form.is_valid():
            form.save()
            messages.success(request, "Hotel details & policies updated successfully.")
            return redirect('staff_panel:website_hotel_details')
        else:
            messages.error(request, "Failed to update hotel details. Please check the errors below.")
    else:
        form = HotelInfoForm(instance=hotel_info)

    return render(request, 'staff_panel/website/hotel_details.html', {
        'form': form,
        'hotel_info': hotel_info,
        'active_tab': 'hotel',
    })


@website_access_required
def website_restaurant_details(request):
    """
    Staff page to manage singleton RestaurantInfo: dining hours, thattukada,
    cuisine description, room service info.
    """
    restaurant_info = RestaurantInfo.load()
    if request.method == 'POST':
        form = RestaurantInfoForm(request.POST, instance=restaurant_info)
        if form.is_valid():
            form.save()
            messages.success(request, "Restaurant details & hours updated successfully.")
            return redirect('staff_panel:website_restaurant_details')
        else:
            messages.error(request, "Failed to update restaurant details. Please check the errors below.")
    else:
        form = RestaurantInfoForm(instance=restaurant_info)

    return render(request, 'staff_panel/website/restaurant_details.html', {
        'form': form,
        'restaurant_info': restaurant_info,
        'active_tab': 'restaurant',
    })


@website_access_required
def website_menu(request):
    """
    Staff page to manage MenuCategories and MenuItems:
    category list + item list with category filter; add/edit/delete for both.
    """
    categories = MenuCategory.objects.all()
    selected_category_id = request.GET.get('category', '').strip()

    items_qs = MenuItem.objects.select_related('category').all()
    selected_category = None
    if selected_category_id:
        try:
            selected_category = categories.get(id=int(selected_category_id))
            items_qs = items_qs.filter(category=selected_category)
        except (ValueError, MenuCategory.DoesNotExist):
            selected_category_id = ''

    category_form = MenuCategoryForm()
    item_form = MenuItemForm()

    edit_category = None
    edit_item = None

    edit_cat_id = request.GET.get('edit_category')
    if edit_cat_id:
        edit_category = get_object_or_404(MenuCategory, id=edit_cat_id)
        if request.method != 'POST':
            category_form = MenuCategoryForm(instance=edit_category)

    edit_item_id = request.GET.get('edit_item')
    if edit_item_id:
        edit_item = get_object_or_404(MenuItem, id=edit_item_id)
        if request.method != 'POST':
            item_form = MenuItemForm(instance=edit_item)
    elif selected_category and request.method != 'POST':
        item_form = MenuItemForm(initial={'category': selected_category})

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_category':
            category_form = MenuCategoryForm(request.POST)
            if category_form.is_valid():
                cat = category_form.save()
                messages.success(request, f"Menu category '{cat.name}' created.")
                return redirect('staff_panel:website_menu')
            else:
                messages.error(request, "Failed to create category. Please check errors.")

        elif action == 'edit_category':
            cat_id = request.POST.get('category_id')
            edit_category = get_object_or_404(MenuCategory, id=cat_id)
            category_form = MenuCategoryForm(request.POST, instance=edit_category)
            if category_form.is_valid():
                category_form.save()
                messages.success(request, f"Category '{edit_category.name}' updated.")
                return redirect('staff_panel:website_menu')
            else:
                messages.error(request, "Failed to update category. Please check errors.")

        elif action == 'create_item':
            item_form = MenuItemForm(request.POST)
            if item_form.is_valid():
                item = item_form.save()
                messages.success(request, f"Menu item '{item.name}' added.")
                redirect_url = f"{request.path}?category={item.category_id}" if item.category_id else request.path
                return redirect(redirect_url)
            else:
                messages.error(request, "Failed to add menu item. Please check errors.")

        elif action == 'edit_item':
            item_id = request.POST.get('item_id')
            edit_item = get_object_or_404(MenuItem, id=item_id)
            item_form = MenuItemForm(request.POST, instance=edit_item)
            if item_form.is_valid():
                item = item_form.save()
                messages.success(request, f"Menu item '{item.name}' updated.")
                redirect_url = f"{request.path}?category={item.category_id}" if item.category_id else request.path
                return redirect(redirect_url)
            else:
                messages.error(request, "Failed to update menu item. Please check errors.")

    return render(request, 'staff_panel/website/menu.html', {
        'categories': categories,
        'items': items_qs,
        'selected_category': selected_category,
        'selected_category_id': selected_category_id,
        'category_form': category_form,
        'item_form': item_form,
        'edit_category': edit_category,
        'edit_item': edit_item,
        'active_tab': 'menu',
    })


@website_access_required
def website_menu_category_delete(request, pk):
    """
    Deletes a menu category. Blocked with a friendly message if category contains items.
    """
    if request.method == 'POST':
        category = get_object_or_404(MenuCategory, pk=pk)
        item_count = category.items.count()
        if item_count > 0:
            messages.error(
                request,
                f"Cannot delete category '{category.name}' because it contains {item_count} menu item(s). "
                f"Please delete or reassign those items first."
            )
            return redirect('staff_panel:website_menu')

        try:
            name = category.name
            category.delete()
            messages.success(request, f"Category '{name}' deleted successfully.")
        except ProtectedError:
            messages.error(
                request,
                f"Cannot delete category '{category.name}' because it still has associated items."
            )
    return redirect('staff_panel:website_menu')


@website_access_required
def website_menu_item_delete(request, pk):
    """
    Deletes a single menu item.
    """
    if request.method == 'POST':
        item = get_object_or_404(MenuItem, pk=pk)
        name = item.name
        cat_id = item.category_id
        item.delete()
        messages.success(request, f"Menu item '{name}' deleted successfully.")
        if cat_id:
            return redirect(f"{redirect('staff_panel:website_menu').url}?category={cat_id}")
    return redirect('staff_panel:website_menu')


@website_access_required
def website_nearby_places(request):
    """
    Staff page to manage NearbyPlace entries: list + add/edit/delete.
    """
    places = NearbyPlace.objects.all()
    form = NearbyPlaceForm()
    edit_id = request.GET.get('edit')
    edit_place = None

    if edit_id:
        edit_place = get_object_or_404(NearbyPlace, id=edit_id)
        if request.method != 'POST':
            form = NearbyPlaceForm(instance=edit_place)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            form = NearbyPlaceForm(request.POST)
            if form.is_valid():
                p = form.save()
                messages.success(request, f"Nearby place '{p.name}' added successfully.")
                return redirect('staff_panel:website_nearby_places')
            else:
                messages.error(request, "Failed to add nearby place. Please check errors.")
        elif action == 'edit':
            p_id = request.POST.get('place_id')
            edit_place = get_object_or_404(NearbyPlace, id=p_id)
            form = NearbyPlaceForm(request.POST, instance=edit_place)
            if form.is_valid():
                form.save()
                messages.success(request, f"Nearby place '{edit_place.name}' updated successfully.")
                return redirect('staff_panel:website_nearby_places')
            else:
                messages.error(request, "Failed to update nearby place. Please check errors.")

    return render(request, 'staff_panel/website/nearby_places.html', {
        'places': places,
        'form': form,
        'edit_place': edit_place,
        'active_tab': 'nearby',
    })


@website_access_required
def website_nearby_place_delete(request, pk):
    """
    Deletes a nearby place entry.
    """
    if request.method == 'POST':
        place = get_object_or_404(NearbyPlace, pk=pk)
        name = place.name
        place.delete()
        messages.success(request, f"Nearby place '{name}' deleted successfully.")
    return redirect('staff_panel:website_nearby_places')


@website_access_required
def website_faqs(request):
    """
    Staff page to manage Chatbot FAQs: list + add/edit/delete + active toggle.
    Supports prefilling question from unanswered questions via ?prefill_question=...
    """
    faqs = ChatFAQ.objects.all()
    form = ChatFAQForm()
    edit_id = request.GET.get('edit')
    edit_faq = None
    prefill_question = request.GET.get('prefill_question', '').strip()

    if edit_id:
        edit_faq = get_object_or_404(ChatFAQ, id=edit_id)
        if request.method != 'POST':
            form = ChatFAQForm(instance=edit_faq)
    elif prefill_question and request.method != 'POST':
        form = ChatFAQForm(initial={'question': prefill_question})

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            form = ChatFAQForm(request.POST)
            if form.is_valid():
                faq = form.save()
                messages.success(request, f"FAQ '{faq.question}' created successfully.")
                # If created from an unanswered question, optionally mark matching question handled
                from_unanswered_id = request.POST.get('from_unanswered_id')
                if from_unanswered_id:
                    UnansweredQuestion.objects.filter(id=from_unanswered_id).update(is_handled=True)
                return redirect('staff_panel:website_faqs')
            else:
                messages.error(request, "Failed to create FAQ. Please check errors.")
        elif action == 'edit':
            faq_id = request.POST.get('faq_id')
            edit_faq = get_object_or_404(ChatFAQ, id=faq_id)
            form = ChatFAQForm(request.POST, instance=edit_faq)
            if form.is_valid():
                form.save()
                messages.success(request, f"FAQ '{edit_faq.question}' updated successfully.")
                return redirect('staff_panel:website_faqs')
            else:
                messages.error(request, "Failed to update FAQ. Please check errors.")

    from_unanswered_id = request.GET.get('from_unanswered_id', '')

    return render(request, 'staff_panel/website/faqs.html', {
        'faqs': faqs,
        'form': form,
        'edit_faq': edit_faq,
        'prefill_question': prefill_question,
        'from_unanswered_id': from_unanswered_id,
        'active_tab': 'faqs',
    })


@website_access_required
def website_faq_toggle(request, pk):
    """
    Toggles the is_active status of a ChatFAQ.
    """
    if request.method == 'POST':
        faq = get_object_or_404(ChatFAQ, pk=pk)
        faq.is_active = not faq.is_active
        faq.save()
        status_label = "activated" if faq.is_active else "deactivated"
        messages.success(request, f"FAQ '{faq.question}' {status_label}.")
    return redirect('staff_panel:website_faqs')


@website_access_required
def website_faq_delete(request, pk):
    """
    Deletes a ChatFAQ.
    """
    if request.method == 'POST':
        faq = get_object_or_404(ChatFAQ, pk=pk)
        question = faq.question
        faq.delete()
        messages.success(request, f"FAQ '{question}' deleted successfully.")
    return redirect('staff_panel:website_faqs')


@website_access_required
def website_unanswered_questions(request):
    """
    Staff page to review questions the chatbot could not answer.
    Lists newest first, with 'Create FAQ from this', 'Mark handled', and 'Delete'.
    """
    questions_qs = UnansweredQuestion.objects.all().order_by('-last_asked')
    handled_filter = request.GET.get('handled', '').strip()
    if handled_filter == '0':
        questions_qs = questions_qs.filter(is_handled=False)
    elif handled_filter == '1':
        questions_qs = questions_qs.filter(is_handled=True)

    paginator = Paginator(questions_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    unhandled_count = UnansweredQuestion.objects.filter(is_handled=False).count()

    return render(request, 'staff_panel/website/unanswered_questions.html', {
        'page_obj': page_obj,
        'handled_filter': handled_filter,
        'unhandled_count': unhandled_count,
        'active_tab': 'unanswered',
    })


@website_access_required
def website_unanswered_handle(request, pk):
    """
    Marks an unanswered question as handled / unhandled.
    """
    if request.method == 'POST':
        q = get_object_or_404(UnansweredQuestion, pk=pk)
        q.is_handled = not q.is_handled
        q.save()
        status_label = "marked as handled" if q.is_handled else "marked as unhandled"
        messages.success(request, f"Question {status_label}.")
    return redirect('staff_panel:website_unanswered_questions')


@website_access_required
def website_unanswered_delete(request, pk):
    """
    Deletes an unanswered question.
    """
    if request.method == 'POST':
        q = get_object_or_404(UnansweredQuestion, pk=pk)
        q.delete()
        messages.success(request, "Unanswered question deleted.")
    return redirect('staff_panel:website_unanswered_questions')

