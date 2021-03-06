# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from okr.forms import ObjectiveForm, KeyResultForm, AuthForm, RegisterForm, ChangePasswordForm
from okr.models import Objective, KeyResult


#############################################################################
# Key Results
#############################################################################

# Auxiliar functions
def get_details(type_data, obtained, expected):
    if type_data == KeyResult.POSITIVE:
        details = 'Obtained %d of %d' % (obtained, expected)
    elif type_data == KeyResult.NEGATIVE:
        details = 'Failed %d of %d' % (obtained, expected)
    elif type_data == KeyResult.BINARY:
        if obtained == 0:
            details = 'No achieved'
        else:
            details = 'Achieved'
    return details


def list_okrs(objectives_list, show_forms=False):
    okr_list = []
    for o in objectives_list:
        key_results_list = KeyResult.objects.filter(objective=o).order_by('-pub_date')

        keyresults = []
        if key_results_list:
            for k in key_results_list:
                keyresults.append({
                    'id': k.id,
                    'name': k.name,
                    'percentage': int(k.percentage),
                    'details': get_details(k.type_data, k.obtained, k.expected),
                })
                if show_forms:
                    keyresults[-1]['form'] = KeyResultForm(instance=k)

        okr_list.append({
            'objective': o,
            'percentage': int(o.percentage_total()),
            'keyresults': keyresults,
        })

    return okr_list


@login_required
def visible(request):
    objectives_list = Objective.objects.filter(
        user=request.user,
        end_date__gte=timezone.now()).order_by('end_date')
    context = {'okr_list': list_okrs(objectives_list, True)}
    return render(request, 'okr/visible.html', context)


@login_required
def archived(request):
    return archived_paged(request, 1)


@login_required
def archived_paged(request, page):
    objectives_list = Objective.objects.filter(user=request.user, end_date__lt=timezone.now()).order_by('end_date')

    okr_list = list_okrs(objectives_list)
    paginator = Paginator(okr_list, 7)

    try:
        okrs = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        okrs = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        okrs = paginator.page(paginator.num_pages)

    return render(request, 'okr/archived.html', {'okr_list': okrs})


@login_required
def edit_kr(request):
    if not request.is_ajax(): raise Http404

    if request.method == 'POST' and request.POST.has_key('id'):
        kr = get_object_or_404(KeyResult, id=request.POST['id'], objective__user=request.user)
        form = KeyResultForm(request.POST, instance=kr)
        if form.is_valid():
            form.save()
            response = {
                'status': 'ok',
                'data': {
                    'name': kr.name,
                    'percentage': int(kr.percentage),
                    'details': get_details(kr.type_data, kr.obtained, kr.expected),
                    'percentage_total': int(kr.objective.percentage_total()),
                }
            }
        else:
            response = {
                'status': 'error',
                'data': form.errors
            }
    else:
        response = {'status': 'method-error'}
    return JsonResponse(response)


@login_required
def show_kr(request, id):
    if not request.is_ajax(): raise Http404
    kr = get_object_or_404(KeyResult, id=id, objective__user=request.user)
    response = {
        'name': kr.name,
        'type_data': kr.type_data,
        'expected': kr.expected,
        'obtained': kr.obtained
    }
    return JsonResponse(response)


@login_required
def add_kr(request, o):
    obj = get_object_or_404(Objective, id=o, user=request.user)
    form = KeyResultForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        kr = form.save(commit=False)
        kr.objective = obj
        kr.save()
        return redirect('okr:index')
    context = {
        'form': form,
        'objective': obj
    }
    return render(request, "okr/add_kr.html", context)


@login_required
def delete_kr(request, id):
    get_object_or_404(KeyResult, pk=id, objective__user=request.user).delete()
    return redirect('okr:index')


#############################################################################
# Objectives
#############################################################################

@login_required
def add_obj(request):
    form = ObjectiveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        o = form.save(commit=False)
        o.user = request.user
        o.save()
        return redirect('okr:index')
    return render(request, "okr/add_obj.html", {'form': form})


@login_required
def edit_obj(request, id):
    obj = get_object_or_404(Objective, id=id, user=request.user)
    if request.method == "POST":
        form = ObjectiveForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect('okr:index')
    else:
        form = ObjectiveForm(instance=obj)
    context = {
        'form': form,
        'objective': obj
    }
    return render(request, "okr/edit_obj.html", context)


@login_required
def delete_obj(request, id):
    get_object_or_404(Objective, pk=id, user=request.user).delete()
    return redirect('okr:index')


#############################################################################
# Users
#############################################################################

def user_login(request):
    if request.user.is_authenticated():
        return redirect('okr:index')

    form = AuthForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid:
        user = form.login(request)
        if user:
            # Username and password are correct and user is marked as "active"
            login(request, user)
            return redirect('okr:index')
    return render(request, 'okr/login.html', {'form': form})


@login_required
def user_logout(request):
    logout(request)
    return redirect('okr:login')


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        # Login
        username = request.POST['username']
        password = request.POST['password1']
        user = authenticate(username=username, password=password)
        login(request, user)
        return redirect('okr:index')
    return render(request, 'okr/register.html', {'form': form})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            return redirect('okr:index')
    else:
        form = ChangePasswordForm(user=request.user)
    return render(request, 'okr/change_password.html', {'form': form})
